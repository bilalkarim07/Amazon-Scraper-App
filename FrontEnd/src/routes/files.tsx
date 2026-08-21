// FrontEnd/src/routes/files.tsx

import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Trash2, Inbox, Loader2, Plus, Pencil, ChevronLeft, ChevronRight } from "lucide-react";
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
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
    DialogDescription,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { downloadFile as downloadFileFromBackend } from "../lib/download";

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
                content: "Browse, download, and manage your scraped Amazon CSV exports.",
            },
        ],
    }),
    component: FilesPage,
});

const PAGE_SIZE = 10;

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

function formatFullDate(timestamp: number) {
    try {
        return new Date(timestamp).toLocaleString(undefined, {
            weekday: "short",
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    } catch {
        return "Unknown date";
    }
}

function validateRenameInput(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return "File name cannot be empty.";
    if (trimmed.length > 180) return "File name is too long.";
    if (trimmed.includes("/") || trimmed.includes("\\")) {
        return "File name cannot contain path separators.";
    }
    if (!/^[a-zA-Z0-9._ -]+$/.test(trimmed)) {
        return "Use only letters, numbers, spaces, dots, hyphens, and underscores.";
    }
    return null;
}

function FilesPage() {
    const {
        files,
        deleteFile,
        renameFile,
        refreshFiles,
        updateFileNote,
    } = useScrape();

    const [loading, setLoading] = useState(true);
    const [pending, setPending] = useState<ScrapedFile | null>(null);
    const [downloading, setDownloading] = useState<string | null>(null);
    const [renameTarget, setRenameTarget] = useState<ScrapedFile | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const [renaming, setRenaming] = useState(false);
    const [noteDialogOpen, setNoteDialogOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState<ScrapedFile | null>(null);
    const [noteDraft, setNoteDraft] = useState("");
    const [page, setPage] = useState(1);

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

    const totalPages = Math.max(1, Math.ceil(files.length / PAGE_SIZE));

    useEffect(() => {
        setPage((current) => Math.min(current, totalPages));
    }, [totalPages]);

    const visibleFiles = useMemo(() => {
        const start = (page - 1) * PAGE_SIZE;
        return files.slice(start, start + PAGE_SIZE);
    }, [files, page]);

    const renameError = useMemo(() => {
        const basicError = validateRenameInput(renameValue);
        if (basicError) return basicError;

        const normalized = (
            renameValue.trim().toLowerCase().endsWith(".csv")
                ? renameValue.trim()
                : `${renameValue.trim()}.csv`
        ).toLowerCase();

        if (
            renameTarget &&
            renameTarget.name.toLowerCase() !== normalized &&
            files.some(
                (file) =>
                    file.id !== renameTarget.id &&
                    file.name.toLowerCase() === normalized,
            )
        ) {
            return "A file with this name already exists.";
        }

        return null;
    }, [files, renameTarget, renameValue]);

    const handleDownload = async (file: ScrapedFile) => {
        setDownloading(file.id);

        try {
            await downloadFileFromBackend(file);
        } catch (err) {
            // downloadFileFromBackend already reports the backend error.
            if (err instanceof Error) {
                console.error("Download failed:", err.message);
            }
        } finally {
            setDownloading(null);
        }
    };

    const handleDelete = async () => {
        if (!pending) return;

        const file = pending;

        try {
            await deleteFile(file.id);
            setPending(null);
        } catch {
            // Store displays the backend error toast.
        }
    };

    const openNoteDialog = (file: ScrapedFile) => {
        setSelectedFile(file);
        setNoteDraft(file.note || "");
        setNoteDialogOpen(true);
    };

    const handleSaveNote = async () => {
        if (!selectedFile) return;

        try {
            await updateFileNote(selectedFile.id, noteDraft);
            setNoteDialogOpen(false);
            setSelectedFile(null);
            setNoteDraft("");
        } catch {
            // Store displays the backend error toast.
        }
    };

    const openRenameDialog = (file: ScrapedFile) => {
        setRenameTarget(file);
        setRenameValue(file.name);
    };

    const handleRename = async () => {
        if (!renameTarget || renameError) return;

        setRenaming(true);

        try {
            await renameFile(renameTarget.id, renameValue);
            setRenameTarget(null);
            setRenameValue("");
        } catch {
            // Store displays the backend error toast.
        } finally {
            setRenaming(false);
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
        <TooltipProvider delayDuration={200}>
            <main className="mx-auto w-full max-w-4xl px-5 py-10 md:py-16">
                {/* PAGE TITLE */}
                <h1 className="title-pop text-3xl md:text-5xl">
                    List of scraped files
                </h1>

                {/* FILE COUNT */}
                <p className="mt-3 text-sm text-muted-foreground">
                    {files.length} file{files.length === 1 ? "" : "s"} stored on this
                    application.
                </p>

                {/* TABLE CARD */}
                <section className="card-hard mt-8 overflow-hidden">
                    <table className="w-full text-left text-sm">
                        <thead className="border-b-2 bg-muted/60 font-display">
                            <tr>
                                <th className="w-14 px-4 py-3">Sr.No</th>
                                <th className="px-4 py-3">File Name</th>
                                <th className="hidden px-4 py-3 sm:table-cell">Rows</th>
                                <th className="px-4 py-3">When</th>
                                <th className="px-4 py-3">Note</th>
                                <th className="px-4 py-3 text-right">Download / Delete</th>
                            </tr>
                        </thead>

                        <tbody>
                            {visibleFiles.map((file, index) => (
                                <tr
                                    key={file.id}
                                    className="border-b-2 border-border/15 transition-colors last:border-0 hover:bg-accent/25"
                                >
                                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                                        {(page - 1) * PAGE_SIZE + index + 1}
                                    </td>

                                    <td className="px-4 py-3 font-medium">
                                        <div className="flex min-w-0 items-center gap-1">
                                            <span className="truncate">{file.name}</span>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <button
                                                        type="button"
                                                        onClick={() => openRenameDialog(file)}
                                                        className="shrink-0 rounded-lg p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-primary"
                                                        aria-label={`Rename ${file.name}`}
                                                    >
                                                        <Pencil className="h-3.5 w-3.5" />
                                                    </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    <p>Rename file</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </div>
                                    </td>

                                    <td className="hidden px-4 py-3 font-mono text-xs sm:table-cell">
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <span className="cursor-help">{file.rows}</span>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>This file contains {file.rows} row{file.rows === 1 ? "" : "s"} of scraped data.</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    </td>

                                    <td className="px-4 py-3 text-muted-foreground">
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <span className="cursor-help">
                                                    {when(file.createdAt)}
                                                </span>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>Scraped on {formatFullDate(file.createdAt)}</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    </td>

                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-1">
                                            {file.note ? (
                                                <span className="max-w-[120px] line-clamp-1 text-sm text-muted-foreground">
                                                    {file.note}
                                                </span>
                                            ) : (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <button
                                                            onClick={() => openNoteDialog(file)}
                                                            className="rounded-lg border-2 border-dashed p-1 text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                                                            aria-label="Add note"
                                                        >
                                                            <Plus className="h-4 w-4" />
                                                        </button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>Add note</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            )}
                                            {file.note && (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <button
                                                            onClick={() => openNoteDialog(file)}
                                                            className="rounded-lg p-1 text-muted-foreground hover:text-primary transition-colors"
                                                            aria-label="Edit note"
                                                        >
                                                            <Pencil className="h-3.5 w-3.5" />
                                                        </button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>Edit note</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            )}
                                        </div>
                                    </td>

                                    <td className="px-4 py-3">
                                        <div className="flex justify-end gap-2">
                                            {/* DOWNLOAD */}
                                            <Tooltip>
                                                <TooltipTrigger asChild>
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
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    <p>Download file</p>
                                                </TooltipContent>
                                            </Tooltip>

                                            {/* DELETE */}
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <button
                                                        onClick={() => setPending(file)}
                                                        aria-label={`Delete ${file.name}`}
                                                        className="rounded-lg border-2 bg-card p-2 text-destructive shadow-[2px_2px_0_0_var(--ink)] press"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    <p>Delete file</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </div>
                                    </td>
                                </tr>
                            ))}

                            {files.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="px-4 py-16 text-center">
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

                    {files.length > PAGE_SIZE && (
                        <div className="flex items-center justify-between border-t-2 border-border/15 px-4 py-3">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        type="button"
                                        onClick={() => setPage((current) => Math.max(1, current - 1))}
                                        disabled={page === 1}
                                        aria-label="Previous files"
                                        className="rounded-lg border-2 bg-card p-2 shadow-[2px_2px_0_0_var(--ink)] press disabled:cursor-not-allowed disabled:opacity-35"
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>Previous page</p>
                                </TooltipContent>
                            </Tooltip>

                            <span className="text-xs text-muted-foreground">
                                Page {page} of {totalPages}
                            </span>

                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        type="button"
                                        onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                                        disabled={page === totalPages}
                                        aria-label="Next files"
                                        className="rounded-lg border-2 bg-card p-2 shadow-[2px_2px_0_0_var(--ink)] press disabled:cursor-not-allowed disabled:opacity-35"
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>Next page</p>
                                </TooltipContent>
                            </Tooltip>
                        </div>
                    )}
                </section>

                {/* DELETE CONFIRMATION */}
                <AlertDialog
                    open={!!pending}
                    onOpenChange={(open) => {
                        if (!open) setPending(null);
                    }}
                >
                    <AlertDialogContent className="border-2">
                        <AlertDialogHeader>
                            <AlertDialogTitle>
                                Delete {pending?.name}?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                                This removes the file from the app list.
                            </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={handleDelete}>
                                Remove
                            </AlertDialogAction>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialog>

                {/* RENAME DIALOG */}
                <Dialog
                    open={!!renameTarget}
                    onOpenChange={(open) => {
                        if (!open && !renaming) {
                            setRenameTarget(null);
                            setRenameValue("");
                        }
                    }}
                >
                    <DialogContent className="border-2 sm:max-w-md">
                        <DialogHeader>
                            <DialogTitle>Rename file</DialogTitle>
                            <DialogDescription>
                                Enter a unique CSV file name.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-2 py-2">
                            <Input
                                value={renameValue}
                                onChange={(event) => setRenameValue(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter" && !renameError && !renaming) {
                                        void handleRename();
                                    }
                                }}
                                autoFocus
                                disabled={renaming}
                                aria-invalid={!!renameError}
                                placeholder="my_scraped_file.csv"
                            />
                            <p
                                className={`text-xs ${
                                    renameError ? "text-destructive" : "text-muted-foreground"
                                }`}
                            >
                                {renameError ||
                                    "The .csv extension will be added automatically if omitted."}
                            </p>
                        </div>

                        <DialogFooter>
                            <button
                                type="button"
                                onClick={() => setRenameTarget(null)}
                                disabled={renaming}
                                className="rounded-lg border-2 px-4 py-2 text-sm press"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleRename()}
                                disabled={!!renameError || renaming}
                                className="rounded-lg border-2 bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-[2px_2px_0_0_var(--ink)] press disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {renaming ? "Renaming…" : "Rename"}
                            </button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* NOTE DIALOG */}
                <Dialog open={noteDialogOpen} onOpenChange={setNoteDialogOpen}>
                    <DialogContent className="border-2">
                        <DialogHeader>
                            <DialogTitle>
                                {selectedFile?.note ? "Edit Note" : "Add Note"} — {selectedFile?.name}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="py-2">
                            <Textarea
                                value={noteDraft}
                                onChange={(event) => setNoteDraft(event.target.value)}
                                placeholder="Add a note about this file..."
                                className="min-h-[100px] resize-y"
                            />
                        </div>
                        <DialogFooter>
                            <button
                                type="button"
                                onClick={() => setNoteDialogOpen(false)}
                                className="rounded-lg border-2 px-4 py-2 text-sm press"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleSaveNote()}
                                className="rounded-lg border-2 bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-[2px_2px_0_0_var(--ink)] press"
                            >
                                Save Note
                            </button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </main>
        </TooltipProvider>
    );
}