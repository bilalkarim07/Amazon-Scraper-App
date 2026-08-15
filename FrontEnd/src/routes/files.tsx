import { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useScrape } from "@/lib/scrape-store";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Download, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

function formatDate(timestamp: number) {
  try {
    return formatDistanceToNow(timestamp, { addSuffix: true });
  } catch {
    return "Unknown";
  }
}

function FilesPage() {
  const { files, deleteFile, downloadFile, refreshFiles } = useScrape();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch files on mount
  useEffect(() => {
    let mounted = true;

    async function fetchFiles() {
      setLoading(true);
      setError(null);
      try {
        await refreshFiles();
      } catch (err: any) {
        if (mounted) {
          const msg = err?.message || "Failed to load files from server";
          setError(msg);
          toast.error(msg);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchFiles();

    return () => {
      mounted = false;
    };
  }, [refreshFiles]);

  const handleDelete = async (id: string) => {
    try {
      await deleteFile(id);
      // State is updated automatically by deleteFile calling refreshFiles
    } catch (err) {
      // Error already toasted in deleteFile
    }
  };

  const handleDownload = async (file: any) => {
    try {
      await downloadFile(file);
    } catch (err) {
      // Error already toasted
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="mt-4 text-sm text-muted-foreground">Loading files…</p>
      </div>
    );
  }

  // Show error state (but keep the page usable)
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-4">
        <p className="text-sm text-red-500">{error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  // Empty state
  if (!files || files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-lg font-semibold">No scraped files yet</p>
        <p className="text-sm text-muted-foreground">
          Your scraped CSV files will appear here after you run a scrape.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">List of scraped files</h2>
        <p className="text-sm text-muted-foreground">
          {files.length} file{files.length !== 1 ? "s" : ""} stored in the backend
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[60px]">Sr.No</TableHead>
              <TableHead>File Name</TableHead>
              <TableHead className="text-right">Rows</TableHead>
              <TableHead className="text-right">When</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {files.map((file, index) => (
              <TableRow key={file.id}>
                <TableCell>{index + 1}</TableCell>
                <TableCell className="font-medium">{file.name}</TableCell>
                <TableCell className="text-right">{file.rows}</TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatDate(file.createdAt)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDownload(file)}
                      title="Download"
                    >
                      <Download className="h-4 w-4" />
                    </Button>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm" title="Delete">
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This will permanently delete the file "{file.name}" from the server.
                            This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(file.id)}>
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ✅ Export the Route for TanStack Router
export const Route = createFileRoute("/files")({
  component: FilesPage,
});