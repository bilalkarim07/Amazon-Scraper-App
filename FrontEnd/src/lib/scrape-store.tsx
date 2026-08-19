import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { ScrapeContext, useScrape } from "./scrape-context";
import { downloadFile, downloadJobOutput } from "./download";

const API_BASE = typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8000"
  : "http://localhost:8000";

const POLL_INTERVAL_MS = 3000;
const QUOTA_REFRESH_INTERVAL_MS = 60000;

export type ScrapedFile = {
  id: string;
  name: string;
  createdAt: number;
  rows: number;
  note?: string;
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
  quickScrape: boolean;
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
  fd.append("quick_scrape", String(opts.quickScrape));
  fd.append("headless", "true");
  return fd;
}

function validateRenameFilename(filename: string): string {
  const trimmed = filename.trim();
  if (!trimmed) throw new Error("File name cannot be empty.");
  if (trimmed.length > 180) throw new Error("File name is too long.");
  if (trimmed.includes("/") || trimmed.includes("\\")) throw new Error("File name cannot contain path separators.");
  if (!/^[a-zA-Z0-9._ -]+$/.test(trimmed)) throw new Error("Use only letters, numbers, spaces, dots, hyphens, and underscores.");
  return trimmed.toLowerCase().endsWith(".csv") ? trimmed : `${trimmed}.csv`;
}

export function ScrapeProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<ScrapedFile[]>([]);
  const [job, setJob] = useState<JobState>({
    status: "idle", jobId: null, done: 0, total: 0, sourceName: "", outputFile: null, error: null,
  });
  const [backendOnline, setBackendOnline] = useState(false);
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    const id = setInterval(check, 10000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const refreshQuota = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/quota`);
      if (res.ok) setQuota(await res.json());
    } catch { /* ignore transient backend errors */ }
  }, []);

  useEffect(() => {
    refreshQuota();
    const id = setInterval(refreshQuota, QUOTA_REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refreshQuota]);

  const refreshFiles = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/files`);
    if (!res.ok) throw new Error(`Failed to fetch files: ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error("Backend returned an invalid files response.");
    setFiles(data.map((item: any) => ({
      id: String(item.id),
      name: item.filename,
      createdAt: new Date(item.created_at).getTime(),
      rows: item.row_count ?? 0,
      note: item.note ?? undefined,
    })));
  }, []);

  const deleteFile = useCallback(async (id: string) => {
    const res = await fetch(`${API_BASE}/api/files/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
    await refreshFiles();
    toast.success("File deleted");
  }, [refreshFiles]);

  const renameFile = useCallback(async (id: string, filename: string) => {
    const normalizedName = validateRenameFilename(filename);
    const current = files.find((file) => file.id === id);
    if (!current) throw new Error("File no longer exists. Refresh the Files page and try again.");
    const conflict = files.some((file) => file.id !== id && file.name.toLowerCase() === normalizedName.toLowerCase());
    if (conflict) throw new Error(`A file named "${normalizedName}" already exists.`);
    if (current.name.toLowerCase() === normalizedName.toLowerCase()) return;
    const res = await fetch(`${API_BASE}/api/files/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: normalizedName }),
    });
    if (!res.ok) {
      let message = `Rename failed: ${res.status}`;
      try { const data = await res.json(); if (typeof data?.detail === "string") message = data.detail; } catch { /* ignore */ }
      throw new Error(message);
    }
    await refreshFiles();
    toast.success(`Renamed to ${normalizedName}`);
  }, [files, refreshFiles]);

  const updateFileNote = useCallback(async (id: string, note: string) => {
    const res = await fetch(`${API_BASE}/api/files/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    });
    if (!res.ok) throw new Error(`Update failed: ${res.status}`);
    await refreshFiles();
    toast.success("Note saved");
  }, [refreshFiles]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollJobStatus = useCallback((jobId: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "completed") {
          stopPolling();
          await refreshFiles().catch(() => undefined);
          setJob((prev) => ({ ...prev, status: "done", done: data.processed_rows ?? data.total_rows ?? 0, total: data.total_rows ?? prev.total, outputFile: data.output_file ?? null }));
          refreshQuota();
        } else if (data.status === "failed") {
          stopPolling();
          setJob((prev) => ({ ...prev, status: "failed", error: data.error ?? "Scraping failed." }));
          refreshQuota();
        } else if (data.status === "cancelled") {
          stopPolling();
          await refreshFiles().catch(() => undefined);
          setJob((prev) => ({ ...prev, status: "cancelled", done: data.processed_rows ?? 0, outputFile: data.output_file ?? null }));
          refreshQuota();
        } else if (data.status === "cancelling") {
          setJob((prev) => ({ ...prev, status: "cancelling" }));
        } else {
          setJob((prev) => ({ ...prev, done: data.processed_rows ?? prev.done, total: data.total_rows ?? prev.total }));
        }
      } catch { /* keep polling through transient network failures */ }
    }, POLL_INTERVAL_MS);
  }, [refreshFiles, refreshQuota, stopPolling]);

  const resetJob = useCallback(() => {
    stopPolling();
    setJob({ status: "idle", jobId: null, done: 0, total: 0, sourceName: "", outputFile: null, error: null });
  }, [stopPolling]);

  const startJob = useCallback(async (opts: {
    file: File;
    sourceName: string;
    rows: number;
    column: string;
    threads: number;
    outputName: string;
    firstPageWait?: number;
    nextPageWait?: number;
    keywords?: string[];
    marketplace: string;
    currencyCode: string;
    currencySymbol: string;
    quickScrape?: boolean;
  }) => {
    stopPolling();
    const quickScrape = Boolean(opts.quickScrape);

    // Normal jobs are quota-limited. Quick Scrape intentionally bypasses this check.
    if (!quickScrape && quota && opts.rows > quota.remaining) {
      throw new Error(`Quota exceeded. You have ${quota.remaining} rows remaining, but requested ${opts.rows} rows.`);
    }

    const fd = buildFormData({
      file: opts.file,
      column: opts.column,
      threads: quickScrape ? 1 : opts.threads,
      firstPageWait: opts.firstPageWait ? opts.firstPageWait * 60 : 150,
      nextPageWait: opts.nextPageWait ?? 5,
      outputName: opts.outputName,
      keywords: opts.keywords ?? [],
      marketplace: opts.marketplace,
      currencyCode: opts.currencyCode,
      currencySymbol: opts.currencySymbol,
      quickScrape,
    });

    try {
      const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: fd });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 429 && errData.detail?.error === "QUOTA_EXCEEDED") {
          const detail = errData.detail;
          throw new Error(`Quota exceeded. Daily limit: ${detail.daily_limit}, Used: ${detail.used}, Remaining: ${detail.remaining}, Requested: ${detail.requested}`);
        }
        throw errData;
      }
      const data = await res.json();
      setJob({ status: "processing", jobId: data.job_id, done: 0, total: opts.rows, sourceName: opts.sourceName, outputFile: null, error: null });
      if (!quickScrape) refreshQuota();
      pollJobStatus(data.job_id);
    } catch (err: any) {
      const detail = err && typeof err === "object" && "detail" in err ? err.detail : err;
      if (detail && typeof detail === "object" && detail.error === "INVALID_COLUMN") throw detail;
      const msg = detail && typeof detail === "object" && detail.message ? detail.message : typeof detail === "string" ? detail : "Failed to create job. Is the backend running?";
      setJob({ status: "failed", jobId: null, done: 0, total: opts.rows, sourceName: opts.sourceName, outputFile: null, error: msg });
      throw new Error(msg);
    }
  }, [pollJobStatus, quota, refreshQuota, stopPolling]);

  const cancelJob = useCallback(async () => {
    if (!job.jobId) { resetJob(); return; }
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${job.jobId}/cancel`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to cancel job");
      }
      setJob((prev) => ({ ...prev, status: "cancelling" }));
      toast.info("Cancelling job...");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to cancel");
    }
  }, [job.jobId, resetJob]);

  useEffect(() => {
    refreshFiles().catch(() => undefined);
  }, [refreshFiles]);
  useEffect(() => () => stopPolling(), [stopPolling]);

  const value = useMemo(() => ({
    files, job, backendOnline, quota, startJob, cancelJob, deleteFile,
    renameFile, downloadFile, refreshFiles, refreshQuota, resetJob, updateFileNote,
  }), [files, job, backendOnline, quota, startJob, cancelJob, deleteFile, renameFile, refreshFiles, refreshQuota, resetJob, updateFileNote]);

  return <ScrapeContext.Provider value={value}>{children}</ScrapeContext.Provider>;
}

export { useScrape };
export { downloadFile, downloadJobOutput };
