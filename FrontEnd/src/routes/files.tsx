import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Download, Trash2, Inbox } from "lucide-react";
import { toast } from "sonner";
import { downloadFile, useScrape, type ScrapedFile } from "../lib/scrape-store";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";

export const Route = createFileRoute("/files")({
  head: () => ({
    meta: [
      { title: "Scraped Files | Amazon Listing Scraper" },
      {
        name: "description",
        content: "Browse, download, and delete the CSV files produced by your scrapes.",
      },
      { property: "og:title", content: "Scraped Files | Amazon Listing Scraper" },
      {
        property: "og:description",
        content: "Browse, download, and delete your scraped Amazon CSV exports.",
      },
    ],
  }),
  component: FilesPage,
});

function when(ts: number) {
  const diff = Date.now() - ts;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return new Date(ts).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function FilesPage() {
  const { files, deleteFile } = useScrape();
  const [pending, setPending] = useState<ScrapedFile | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = async (f: ScrapedFile) => {
    setDownloading(f.id);
    try {
      await downloadFile(f);
      toast.success(`Downloading ${f.name}`);
    } catch (err) {
      toast.error(
        `Download failed: ${err instanceof Error ? err.message : "Backend may be offline."}`,
      );
    } finally {
      setDownloading(null);
    }
  };

  return (
    <main className="mx-auto w-full max-w-4xl px-5 py-10 md:py-16">
      <h1 className="title-pop text-3xl md:text-5xl">List of scraped files</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        {files.length} file{files.length === 1 ? "" : "s"} stored on this device.
      </p>

      <section className="card-hard mt-8 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b-2 bg-muted/60 font-display">
            <tr>
              <th className="px-4 py-3 w-14">Sr.No</th>
              <th className="px-4 py-3">File Name</th>
              <th className="px-4 py-3 hidden sm:table-cell">Rows</th>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3 text-right">Download / Delete</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f, i) => (
              <tr
                key={f.id}
                className="border-b-2 border-border/15 transition-colors last:border-0 hover:bg-accent/25"
              >
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {i + 1}
                </td>
                <td className="px-4 py-3 font-medium">{f.name}</td>
                <td className="px-4 py-3 hidden sm:table-cell font-mono text-xs">
                  {f.rows}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{when(f.createdAt)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => handleDownload(f)}
                      disabled={downloading === f.id}
                      aria-label={`Download ${f.name}`}
                      className="rounded-lg border-2 bg-primary p-2 shadow-[2px_2px_0_0_var(--ink)] press disabled:opacity-50"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setPending(f)}
                      aria-label={`Delete ${f.name}`}
                      className="rounded-lg border-2 bg-card p-2 text-destructive shadow-[2px_2px_0_0_var(--ink)] press"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {files.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-16 text-center">
                  <Inbox className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                  <p className="font-display font-semibold">No scraped files yet</p>
                  <p className="text-xs text-muted-foreground">
                    Run a scrape and your exports will land here.
                  </p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <AlertDialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <AlertDialogContent className="border-2">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {pending?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the file from the app list. The output CSV on disk is not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pending) {
                  deleteFile(pending.id);
                  toast.success("File removed from list");
                }
                setPending(null);
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
