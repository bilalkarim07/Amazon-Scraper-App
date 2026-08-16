import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Trash2, Inbox, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useScrape } from "@/lib/scrape-store";
import type { ScrapedFile } from "@/lib/scrape-store";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { downloadFile } from "../lib/download";

export const Route = createFileRoute("/files")({
  head: () => ({
    meta: [
      { title: "Scraped Files | Amazon Listing Scraper" },
      {
        name: "description",
        content:
          "Browse, download, and delete the CSV files produced by your scrapes.",
      },
      {
        property: "og:title",
        content: "Scraped Files | Amazon Listing Scraper",
      },
      {
        property: "og:description",
        content: "Browse, download, and delete your scraped Amazon CSV exports.",
      },
    ],
  }),
  component: FilesPage,
});

function when(timestamp: number) {
  try {
    const diff = Date.now() - timestamp;
    const mins = Math.round(diff / 60000);

    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;

    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs} hr ago`;

    const days = Math.round(hrs / 24);
    if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;

    return new Date(timestamp).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "Unknown";
  }
}

function FilesPage() {
  const {
    files,
    deleteFile,
    downloadFile,
    refreshFiles,
  } = useScrape();

  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<ScrapedFile | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  // Refresh files from backend whenever the Files page is opened.
  useEffect(() => {
    let mounted = true;

    async function loadFiles() {
      setLoading(true);

      try {
        await refreshFiles();
      } catch (err: any) {
        if (mounted) {
          toast.error(
            err?.message || "Failed to load scraped files from the backend.",
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadFiles();

    return () => {
      mounted = false;
    };
  }, [refreshFiles]);

  const handleDownload = async (file: ScrapedFile) => {
    setDownloading(file.id);

    try {
      await downloadFile(file);
      toast.success(`Downloading ${file.name}`);
    } catch (err) {
      toast.error(
        `Download failed: ${
          err instanceof Error
            ? err.message
            : "Backend may be offline."
        }`,
      );
    } finally {
      setDownloading(null);
    }
  };

  const handleDelete = async () => {
    if (!pending) return;

    const file = pending;

    try {
      await deleteFile(file.id);
      toast.success("File removed from list");
    } catch (err) {
      toast.error(
        `Delete failed: ${
          err instanceof Error ? err.message : "Unknown error"
        }`,
      );
    } finally {
      setPending(null);
    }
  };

  if (loading) {
    return (
      <main className="mx-auto flex w-full max-w-4xl items-center justify-center px-5 py-16">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
        <span className="ml-3 text-sm text-muted-foreground">
          Loading files…
        </span>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl px-5 py-10 md:py-16">
      {/* PAGE TITLE */}
      <h1 className="title-pop text-3xl md:text-5xl">
        List of scraped files
      </h1>

      {/* FILE COUNT */}
      <p className="mt-3 text-sm text-muted-foreground">
        {files.length} file{files.length === 1 ? "" : "s"} stored on this
        device.
      </p>

      {/* TABLE CARD */}
      <section className="card-hard mt-8 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b-2 bg-muted/60 font-display">
            <tr>
              <th className="w-14 px-4 py-3">Sr.No</th>

              <th className="px-4 py-3">
                File Name
              </th>

              <th className="hidden px-4 py-3 sm:table-cell">
                Rows
              </th>

              <th className="px-4 py-3">
                When
              </th>

              <th className="px-4 py-3 text-right">
                Download / Delete
              </th>
            </tr>
          </thead>

          <tbody>
            {/* FILES */}
            {files.map((file, index) => (
              <tr
                key={file.id}
                className="border-b-2 border-border/15 transition-colors last:border-0 hover:bg-accent/25"
              >
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {index + 1}
                </td>

                <td className="px-4 py-3 font-medium">
                  {file.name}
                </td>

                <td className="hidden px-4 py-3 font-mono text-xs sm:table-cell">
                  {file.rows}
                </td>

                <td className="px-4 py-3 text-muted-foreground">
                  {when(file.createdAt)}
                </td>

                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {/* DOWNLOAD */}
                    <button
                      onClick={() => handleDownload(file)}
                      disabled={downloading === file.id}
                      aria-label={`Download ${file.name}`}
                      className="rounded-lg border-2 bg-primary p-2 shadow-[2px_2px_0_0_var(--ink)] press disabled:opacity-50"
                    >
                      {downloading === file.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </button>

                    {/* DELETE */}
                    <button
                      onClick={() => setPending(file)}
                      aria-label={`Delete ${file.name}`}
                      className="rounded-lg border-2 bg-card p-2 text-destructive shadow-[2px_2px_0_0_var(--ink)] press"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}

            {/* EMPTY STATE */}
            {files.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-16 text-center"
                >
                  <Inbox className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />

                  <p className="font-display font-semibold">
                    No scraped files yet
                  </p>

                  <p className="text-xs text-muted-foreground">
                    Run a scrape and your exports will land here.
                  </p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* DELETE CONFIRMATION */}
      <AlertDialog
        open={!!pending}
        onOpenChange={(open) => {
          if (!open) {
            setPending(null);
          }
        }}
      >
        <AlertDialogContent className="border-2">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {pending?.name}?
            </AlertDialogTitle>

            <AlertDialogDescription>
              This removes the file from the app list. The output CSV on
              disk will also be removed according to the backend file
              management rules.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter>
            <AlertDialogCancel>
              Cancel
            </AlertDialogCancel>

            <AlertDialogAction onClick={handleDelete}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
