import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { DirectoryExplorer } from "@/components/directory-explorer";
import { useScrape } from "@/lib/scrape-store";
import type { ScrapedFile } from "@/lib/scrape-store";

export const Route = createFileRoute("/files")({
  head: () => ({
    meta: [
      { title: "Files | Amazon Listing Scraper" },
      { name: "description", content: "Browse and manage files in your application working directory." },
      { property: "og:title", content: "Files | Amazon Listing Scraper" },
      { property: "og:description", content: "Browse and manage files in your application working directory." },
    ],
  }),
  component: FilesPage,
});

function FilesPage() {
  const { files, deleteFile, downloadFile, refreshFiles } = useScrape();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    void refreshFiles()
      .catch((error) => {
        if (mounted) toast.error(error instanceof Error ? error.message : "Failed to load files.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [refreshFiles]);

  const handleDownload = async (file: ScrapedFile) => {
    try {
      await downloadFile(file);
      toast.success(`Downloading ${file.name}`);
    } catch (error) {
      toast.error(`Download failed: ${error instanceof Error ? error.message : "Backend may be offline."}`);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteFile(id);
      toast.success("File removed");
    } catch (error) {
      toast.error(`Delete failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  };

  if (loading) {
    return (
      <main className="mx-auto flex w-full max-w-5xl items-center justify-center px-5 py-16">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
        <span className="ml-3 text-sm text-muted-foreground">Loading directory…</span>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl px-5 py-10 md:py-16">
      <h1 className="title-pop text-3xl md:text-5xl">Files</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        Your application working directory. Organize scraped files, folders, and Google Sheets in one place.
      </p>
      <div className="mt-8">
        <DirectoryExplorer files={files} onDownload={handleDownload} onDeleteFile={handleDelete} />
      </div>
    </main>
  );
}
