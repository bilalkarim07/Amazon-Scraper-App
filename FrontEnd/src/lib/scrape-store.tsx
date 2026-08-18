// FrontEnd/src/lib/scrape-store.tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

// Import context and hook from the separate module
import { ScrapeContext, useScrape } from "./scrape-context";
// Import download functions from their dedicated module
import { downloadFile, downloadJobOutput } from "./download";

const API_BASE =
  typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "http://localhost:8000";

const POLL_INTERVAL_MS = 3000;
const QUOTA_REFRESH_INTERVAL_MS = 60000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ScrapedFile = {
  id: string;          // backend file id (int) as string
  name: string;
  createdAt: number;   // timestamp in ms
  rows: number;
  note?: string;       // 👈 NEW: user-provided note for the file
};

export type JobState = {
  status: "idle" | "processing" | "cancelling" | "done" | "failed" | "cancelled";
  jobId: string | null;
  done: number;
  total: number;
  sourceName: string;
  outputFile: string | null;
  error: string | null;
};

export type QuotaState = {
  limit: number;
  used: number;
  remaining: number;
  date: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildFormData(opts: {
  file: File;
  column: string;
  threads: number;
  firstPageWait: number;
  nextPageWait: number;
  outputName: string;
  keywords: string[];
  marketplace: string;
  currencyCode: string;
  currencySymbol: string;
}): FormData {
  const fd = new FormData();
  fd.append("file", opts.file);
  fd.append("column", opts.column);
  fd.append("threads", String(opts.threads));
  fd.append("first_page_wait", String(opts.firstPageWait));
  fd.append("next_page_wait", String(opts.nextPageWait));
  fd.append("output_filename", opts.outputName);
  fd.append("keywords", opts.keywords.join(","));
  fd.append("marketplace", opts.marketplace);
  fd.append("currency_code", opts.currencyCode);
  fd.append("currency_symbol", opts.currencySymbol);
  return fd;
}

function validateRenameFilename(filename: string): string {
  const trimmed = filename.trim();

  if (!trimmed) throw new Error("File name cannot be empty.");
  if (trimmed.length > 180) throw new Error("File name is too long.");
  if (trimmed.includes("/") || trimmed.includes("\\")) {
    throw new Error("File name cannot contain path separators.");
  }
  if (!/^[a-zA-Z0-9._ -]+$/.test(trimmed)) {
    throw new Error("Use only letters, numbers, spaces, dots, hyphens, and underscores.");
  }

  return trimmed.toLowerCase().endsWith(".csv") ? trimmed : `${trimmed}.csv`;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ScrapeProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<ScrapedFile[]>([]);
  const [job, setJob] = useState<JobState>({
    status: "idle",
    jobId: null,
    done: 0,
    total: 0,
    sourceName: "",
    outputFile: null,
    error: null,
  });
  const [backendOnline, setBackendOnline] = useState(false);
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---- Backend health check ----
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        await fetch(`${API_BASE}/api/health`, { mode: "no-cors" });
        if (mounted) setBackendOnline(true);
      } catch {
        if (mounted) setBackendOnline(false);
      }
    };
    check();
    const id = setInterval(check, 10_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  // ---- Quota refresh ----
  const refreshQuota = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/quota`);
      if (res.ok) {
        const data = await res.json();
        setQuota(data);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refreshQuota();
    const interval = setInterval(refreshQuota, QUOTA_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshQuota]);

  // ---- REFRESH FILES (fetch from backend) ----
  const refreshFiles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/files`);
      if (!res.ok) {
        throw new Error(`Failed to fetch files: ${res.status} ${res.statusText}`);
      }
      const data = await res.json();
      if (!Array.isArray(data)) {
        throw new Error("Backend returned non-array response for /api/files");
      }
      const mapped: ScrapedFile[] = data.map((item: any) => ({
        id: String(item.id),
        name: item.filename,
        createdAt: new Date(item.created_at).getTime(),
        rows: item.row_count ?? 0,
        note: item.note ?? undefined,  // 👈 map note from backend
      }));
      setFiles(mapped);
    } catch (err) {
      console.error("refreshFiles error:", err);
      throw err;
    }
  }, []);

  // ---- DELETE FILE (calls backend + refresh) ----
  const deleteFile = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/files/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(`Delete failed: ${res.status}`);
      }
      await refreshFiles();
      toast.success("File deleted");
    } catch (err: any) {
      console.error("Delete error:", err);
      toast.error(err.message || "Delete failed");
      throw err;
    }
  }, [refreshFiles]);

  // ---- RENAME FILE ----
  const renameFile = useCallback(async (id: string, filename: string) => {
    const normalizedName = validateRenameFilename(filename);
    const current = files.find((file) => file.id === id);

    if (!current) {
      throw new Error("File no longer exists. Refresh the Files page and try again.");
    }

    const conflict = files.some(
      (file) =>
        file.id !== id &&
        file.name.trim().toLocaleLowerCase() === normalizedName.toLocaleLowerCase(),
    );

    if (conflict) {
      throw new Error(`A file named "${normalizedName}" already exists.`);
    }

    if (current.name.toLocaleLowerCase() === normalizedName.toLocaleLowerCase()) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/files/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: normalizedName }),
      });

      if (!res.ok) {
        let message = `Rename failed: ${res.status}`;
        try {
          const data = await res.json();
          if (typeof data?.detail === "string") message = data.detail;
        } catch {
          // Keep the fallback message when the backend response is not JSON.
        }
        throw new Error(message);
      }

      await refreshFiles();
      toast.success(`Renamed to ${normalizedName}`);
    } catch (err: any) {
      console.error("Rename error:", err);
      toast.error(err?.message || "Failed to rename file");
      throw err;
    }
  }, [files, refreshFiles]);

  // ---- UPDATE FILE NOTE ----
  const updateFileNote = useCallback(async (id: string, note: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/files/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      if (!res.ok) {
        throw new Error(`Update failed: ${res.status}`);
      }
      // Refresh the file list to show the updated note
      await refreshFiles();
      toast.success("Note saved");
    } catch (err: any) {
      console.error("Update note error:", err);
      toast.error(err.message || "Failed to save note");
      throw err;
    }
  }, [refreshFiles]);

  // ---- Polling helpers ----
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollJobStatus = useCallback(
    (jobId: string, sourceName: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
          if (!res.ok) return;
          const data = await res.json();

          if (data.status === "completed") {
            stopPolling();
            try {
              await refreshFiles();
            } catch (err) {
              console.warn("Failed to refresh files after job completion", err);
            }
            setJob((prev) => ({
              ...prev,
              status: "done",
              done: data.processed_rows ?? data.total_rows ?? 0,
              total: data.total_rows ?? 0,
              outputFile: data.output_file ?? null,
            }));
            refreshQuota();
          } else if (data.status === "failed") {
            stopPolling();
            setJob((prev) => ({
              ...prev,
              status: "failed",
              error: data.error ?? "Scraping failed.",
            }));
            refreshQuota();
          } else if (data.status === "cancelled") {
            stopPolling();
            const processedRows = data.processed_rows ?? 0;
            setJob((prev) => ({
              ...prev,
              status: "cancelled",
              done: processedRows,
              total: prev.total,
              outputFile: data.output_file ?? null,
              error: null,
            }));
            try {
              await refreshFiles();
            } catch (err) {
              console.warn("Failed to refresh files after cancellation", err);
            }
            refreshQuota();
          } else if (data.status === "cancelling") {
            setJob((prev) => ({ ...prev, status: "cancelling" }));
          } else {
            setJob((prev) => ({
              ...prev,
              done: data.processed_rows ?? prev.done,
              total: data.total_rows ?? prev.total,
            }));
          }
        } catch {
          // network blip — keep polling
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling, refreshFiles, refreshQuota]
  );

  // ---- resetJob ----
  const resetJob = useCallback(() => {
    stopPolling();
    setJob({
      status: "idle",
      jobId: null,
      done: 0,
      total: 0,
      sourceName: "",
      outputFile: null,
      error: null,
    });
  }, [stopPolling]);

  // ---- startJob ----
  const startJob = useCallback(
    async ({
      file,
      sourceName,
      rows,
      column,
      threads,
      outputName,
      firstPageWait,
      nextPageWait,
      keywords,
      marketplace,
      currencyCode,
      currencySymbol,
    }) => {
      stopPolling();

      if (quota && rows > quota.remaining) {
        throw new Error(
          `Quota exceeded. You have ${quota.remaining} rows remaining, but requested ${rows} rows.`
        );
      }

      const fd = buildFormData({
        file,
        column,
        threads,
        firstPageWait: firstPageWait ? firstPageWait * 60 : 150,
        nextPageWait: nextPageWait ?? 5,
        outputName,
        keywords: keywords ?? [],
        marketplace,
        currencyCode,
        currencySymbol,
      });

      try {
        const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: fd });
        if (!res.ok) {
          const errData = await res.json();
          if (res.status === 429 && errData.detail?.error === "QUOTA_EXCEEDED") {
            const detail = errData.detail;
            throw new Error(
              `Quota exceeded. Daily limit: ${detail.daily_limit}, Used: ${detail.used}, Remaining: ${detail.remaining}, Requested: ${detail.requested}`
            );
          }
          throw errData;
        }
        const data: { job_id: string; status: string } = await res.json();
        setJob({
          status: "processing",
          jobId: data.job_id,
          done: 0,
          total: rows,
          sourceName,
          outputFile: null,
          error: null,
        });
        refreshQuota();
        pollJobStatus(data.job_id, sourceName);
      } catch (err: any) {
        const detail = err && typeof err === "object" && "detail" in err ? err.detail : err;
        if (detail && typeof detail === "object" && detail.error === "INVALID_COLUMN") {
          throw detail;
        }
        const msg =
          detail && typeof detail === "object" && detail.message
            ? detail.message
            : typeof detail === "string"
            ? detail
            : "Failed to create job. Is the backend running?";
        setJob({
          status: "failed",
          jobId: null,
          done: 0,
          total: rows,
          sourceName,
          outputFile: null,
          error: msg,
        });
        throw new Error(msg);
      }
    },
    [stopPolling, pollJobStatus, quota, refreshQuota]
  );

  // ---- cancelJob ----
  const cancelJob = useCallback(async () => {
    if (!job.jobId) {
      stopPolling();
      resetJob();
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${job.jobId}/cancel`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to cancel job");
      }
      setJob((prev) => ({ ...prev, status: "cancelling" }));
      toast.info("Cancelling job...");
      refreshQuota();
      try {
        await refreshFiles();
      } catch (err) {
        console.warn("Failed to refresh files after cancel request", err);
      }
    } catch (error) {
      console.error("Cancel error:", error);
      toast.error(error instanceof Error ? error.message : "Failed to cancel");
    }
  }, [job.jobId, stopPolling, refreshQuota, resetJob, refreshFiles]);

  // ---- Initial load: fetch files on mount (client-only) ----
  useEffect(() => {
    if (typeof window !== "undefined") {
      refreshFiles().catch((err) => {
        console.warn("Initial files fetch failed:", err);
      });
    }
  }, [refreshFiles]);

  // Cleanup polling on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  const value = useMemo(
    () => ({
      files,
      job,
      backendOnline,
      quota,
      startJob,
      cancelJob,
      deleteFile,
      renameFile,
      downloadFile,
      refreshFiles,
      refreshQuota,
      resetJob,
      updateFileNote,  // 👈 NEW: expose the note update function
    }),
    [
      files,
      job,
      backendOnline,
      quota,
      startJob,
      cancelJob,
      deleteFile,
      renameFile,
      refreshFiles,
      refreshQuota,
      resetJob,
      updateFileNote,
    ]
  );

  return <ScrapeContext.Provider value={value}>{children}</ScrapeContext.Provider>;
}

// ---------------------------------------------------------------------------
// Re‑export the hook (so external imports stay the same)
// ---------------------------------------------------------------------------

export { useScrape };