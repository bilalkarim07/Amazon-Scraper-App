import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner"; // added import for toast

const API_BASE =
  typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "http://localhost:8000";

// How often to poll GET /api/jobs/{id} while a job is running (ms)
const POLL_INTERVAL_MS = 3000;
// How often to refresh quota (ms)
const QUOTA_REFRESH_INTERVAL_MS = 60000; // 1 minute

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A completed scrape result stored in local state. */
export type ScrapedFile = {
  id: string;        // job_id from the backend
  name: string;      // output filename
  createdAt: number; // unix timestamp (ms)
  rows: number;      // total_rows from the backend
};

/** The full job lifecycle tracked in the frontend. */
export type JobState = {
  status: "idle" | "processing" | "cancelling" | "done" | "failed";
  jobId: string | null;
  done: number;           // processed_rows
  total: number;          // total_rows
  sourceName: string;
  outputFile: string | null;
  error: string | null;
};

/** Quota status from the backend. */
export type QuotaState = {
  limit: number;
  used: number;
  remaining: number;
  date: string;
};

type Ctx = {
  files: ScrapedFile[];
  job: JobState;
  backendOnline: boolean;
  quota: QuotaState | null;
  startJob: (opts: {
    file: File;
    sourceName: string;
    rows: number;
    column: string;
    threads: number;
    outputName: string;
    firstPageWait?: number | undefined;
    nextPageWait?: number | undefined;
    keywords?: string[] | undefined;
    marketplace: string;
    currencyCode: string;
    currencySymbol: string;
  }) => Promise<void>;
  cancelJob: () => Promise<void>;
  deleteFile: (id: string) => void;
  refreshQuota: () => Promise<void>;
};

const ScrapeContext = createContext<Ctx | null>(null);

const FILES_STORAGE_KEY = "amz-scraper-files-v2";

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
  // Append marketplace and currency fields
  fd.append("marketplace", opts.marketplace);
  fd.append("currency_code", opts.currencyCode);
  fd.append("currency_symbol", opts.currencySymbol);
  // For development, we want headless=false; but we'll let the backend decide via env.
  // fd.append("headless", "false");
  return fd;
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

  // ---- Persist files list to localStorage (metadata only, no CSV data) ----
  useEffect(() => {
    try {
      const raw = localStorage.getItem(FILES_STORAGE_KEY);
      if (raw) setFiles(JSON.parse(raw) as ScrapedFile[]);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(FILES_STORAGE_KEY, JSON.stringify(files));
    } catch { /* ignore */ }
  }, [files]);

  // ---- Backend health check on mount ----
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        await fetch(`${API_BASE}/api/health`, { mode: "no-cors" });
        if (mounted) setBackendOnline(true);
      } catch (err) {
        console.error("Health check failed:", err);
        if (mounted) setBackendOnline(false);
      }
    };
    check();
    const id = setInterval(check, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  // ---- Quota refresh ----
  const refreshQuota = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/quota`);
      if (res.ok) {
        const data = await res.json();
        setQuota(data);
      } else {
        console.warn("Failed to fetch quota:", res.status);
      }
    } catch (err) {
      console.error("Failed to fetch quota:", err);
    }
  }, []);

  // Refresh quota on mount and periodically
  useEffect(() => {
    refreshQuota();
    const interval = setInterval(refreshQuota, QUOTA_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshQuota]);

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
          if (!res.ok) return; // transient error — keep polling

          const data = await res.json();

          if (data.status === "completed") {
            stopPolling();
            const newFile: ScrapedFile = {
              id: jobId,
              name: data.output_file
                ? data.output_file.split(/[\\/]/).pop() ?? "output.csv"
                : "output.csv",
              createdAt: Date.now(),
              rows: data.total_rows ?? 0,
            };
            setFiles((f) => [newFile, ...f]);
            setJob((prev) => ({
              ...prev,
              status: "done",
              done: data.processed_rows ?? data.total_rows ?? 0,
              total: data.total_rows ?? 0,
              outputFile: data.output_file ?? null,
            }));
            // Refresh quota after job completes
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
            setJob((prev) => ({
              ...prev,
              status: "idle",
              jobId: null,
              done: 0,
              total: 0,
              sourceName: "",
              outputFile: null,
              error: null,
            }));
            if (data.output_file) {
              const newFile: ScrapedFile = {
                id: jobId,
                name: data.output_file.split(/[\\/]/).pop() ?? "output.csv",
                createdAt: Date.now(),
                rows: data.processed_rows ?? 0,
              };
              setFiles((f) => [newFile, ...f]);
            }
            refreshQuota();
          } else if (data.status === "cancelling") {
            setJob((prev) => ({ ...prev, status: "cancelling" }));
          } else {
            // still running or created — update progress counters
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
    [stopPolling, refreshQuota],
  );

  // ---- startJob ----
  const startJob: Ctx["startJob"] = useCallback(
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

      // --- Check quota before submitting ---
      if (quota && rows > quota.remaining) {
        throw new Error(
          `Quota exceeded. You have ${quota.remaining} rows remaining, but requested ${rows} rows.`
        );
      }

      const fd = buildFormData({
        file,
        column,
        threads,
        firstPageWait: firstPageWait ? firstPageWait * 60 : 150, // minutes → seconds
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
          // Handle quota exceeded error from backend
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

        // Refresh quota after job starts (reserved rows)
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
    [stopPolling, pollJobStatus, quota, refreshQuota],
  );

  // ---- cancelJob — calls backend cancel endpoint ----
  const cancelJob = useCallback(async () => {
    if (!job.jobId) {
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
      // Refresh quota after cancellation
      refreshQuota();
    } catch (error) {
      console.error("Cancel error:", error);
      toast.error(error instanceof Error ? error.message : "Failed to cancel");
    }
  }, [job.jobId, stopPolling, refreshQuota]);

  const deleteFile = useCallback((id: string) => {
    setFiles((f) => f.filter((x) => x.id !== id));
  }, []);

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
      refreshQuota,
    }),
    [files, job, backendOnline, quota, startJob, cancelJob, deleteFile, refreshQuota],
  );

  return <ScrapeContext.Provider value={value}>{children}</ScrapeContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useScrape() {
  const ctx = useContext(ScrapeContext);
  if (!ctx) throw new Error("useScrape must be used inside ScrapeProvider");
  return ctx;
}

// ---------------------------------------------------------------------------
// Download helper — fetches from the backend instead of from memory
// ---------------------------------------------------------------------------

export async function downloadFile(file: ScrapedFile): Promise<void> {
  const url = `${API_BASE}/api/jobs/${file.id}/download`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = file.name;
  a.click();
  URL.revokeObjectURL(objectUrl);
}