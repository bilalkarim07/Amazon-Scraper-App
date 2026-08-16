// FrontEnd/src/lib/download.ts
import { toast } from "sonner";
import type { ScrapedFile } from "./scrape-store";

const API_BASE =
  typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "http://localhost:8000";

// ---------------------------------------------------------------------------
// downloadFile — used by the Files page (relies on file.id as integer)
// ---------------------------------------------------------------------------

export async function downloadFile(file: ScrapedFile): Promise<void> {
  try {
    const url = `${API_BASE}/api/files/${file.id}/download`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Download failed: ${res.status}`);
    }
    const disposition = res.headers.get("content-disposition");
    let filename = file.name;
    if (disposition) {
      const match = disposition.match(/filename="?(.+)"?/);
      if (match) filename = match[1];
    }
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    toast.success(`Downloaded ${filename}`);
  } catch (err: any) {
    console.error("Download error:", err);
    toast.error(err.message || "Download failed");
    throw err;
  }
}

// ---------------------------------------------------------------------------
// downloadJobOutput — used by the Scrape Result page (uses job UUID)
// ---------------------------------------------------------------------------

export async function downloadJobOutput(jobId: string): Promise<void> {
  try {
    const url = `${API_BASE}/api/jobs/${jobId}/download`;
    const res = await fetch(url);

    if (!res.ok) {
      let detail = `Download failed: ${res.status}`;
      try {
        const errData = await res.json();
        if (errData.detail) detail = errData.detail;
      } catch {
        // ignore JSON parse error
      }
      throw new Error(detail);
    }

    const disposition = res.headers.get("content-disposition");
    let filename = "output.csv";
    if (disposition) {
      const match = disposition.match(/filename="?(.+)"?/);
      if (match) filename = match[1];
    }

    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

    toast.success(`Downloaded ${filename}`);
  } catch (err: any) {
    console.error("Download error:", err);
    toast.error(err.message || "Download failed");
    throw err;
  }
}