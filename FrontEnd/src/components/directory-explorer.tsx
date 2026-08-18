import { useMemo, useRef, useState } from "react";
import {
  ChevronRight,
  File,
  Folder,
  FolderPlus,
  MoreVertical,
  Pencil,
  Plus,
  Sheet,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { childrenOf, isGoogleSheetUrl, ROOT_DIRECTORY_ID, type DirectoryNode } from "@/lib/directory";
import type { ScrapedFile } from "@/lib/scrape-store";

interface DirectoryExplorerProps {
  files: ScrapedFile[];
  onDownload: (file: ScrapedFile) => void;
  onDeleteFile: (id: string) => Promise<void>;
}

type DialogMode = "folder" | "sheet" | "rename" | null;

export function DirectoryExplorer({ files, onDownload, onDeleteFile }: DirectoryExplorerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [folders, setFolders] = useState<DirectoryNode[]>([]);
  const [sheets, setSheets] = useState<DirectoryNode[]>([]);
  const [currentId, setCurrentId] = useState(ROOT_DIRECTORY_ID);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [name, setName] = useState("");
  const [sheetUrl, setSheetUrl] = useState("");

  const nodes = useMemo<DirectoryNode[]>(() => [
    ...folders,
    ...sheets,
    ...files.map((file) => ({
      id: `file:${file.id}`,
      parentId: ROOT_DIRECTORY_ID,
      name: file.name,
      type: "file" as const,
      rows: file.rows,
      createdAt: file.createdAt,
    })),
  ], [files, folders, sheets]);

  const currentChildren = childrenOf(nodes, currentId === ROOT_DIRECTORY_ID ? null : currentId);
  const selectedNode = nodes.find((node) => node.id === selectedId) ?? null;

  const breadcrumb = useMemo(() => {
    const result: DirectoryNode[] = [];
    let id = currentId;
    while (id !== ROOT_DIRECTORY_ID) {
      const node = nodes.find((item) => item.id === id);
      if (!node) break;
      result.unshift(node);
      id = node.parentId ?? ROOT_DIRECTORY_ID;
    }
    return result;
  }, [currentId, nodes]);

  const createFolder = () => {
    setName("");
    setDialogMode("folder");
  };

  const addSheet = () => {
    setName("");
    setSheetUrl("");
    setDialogMode("sheet");
  };

  const renameSelected = () => {
    if (!selectedNode) return;
    setName(selectedNode.name);
    setDialogMode("rename");
  };

  const submitDialog = () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("A name is required.");
      return;
    }

    if (dialogMode === "folder") {
      setFolders((current) => [...current, {
        id: `folder:${crypto.randomUUID()}`,
        parentId: currentId === ROOT_DIRECTORY_ID ? ROOT_DIRECTORY_ID : currentId,
        name: trimmedName,
        type: "folder",
        createdAt: Date.now(),
      }]);
      toast.success(`Created ${trimmedName}`);
    } else if (dialogMode === "sheet") {
      if (!isGoogleSheetUrl(sheetUrl)) {
        toast.error("Enter a valid Google Sheets URL.");
        return;
      }
      setSheets((current) => [...current, {
        id: `sheet:${crypto.randomUUID()}`,
        parentId: currentId === ROOT_DIRECTORY_ID ? ROOT_DIRECTORY_ID : currentId,
        name: trimmedName,
        type: "google_sheet",
        url: sheetUrl.trim(),
        createdAt: Date.now(),
      }]);
      toast.success(`Added ${trimmedName}`);
    } else if (dialogMode === "rename" && selectedNode) {
      if (selectedNode.type === "folder") {
        setFolders((current) => current.map((node) => node.id === selectedNode.id ? { ...node, name: trimmedName } : node));
      } else if (selectedNode.type === "google_sheet") {
        setSheets((current) => current.map((node) => node.id === selectedNode.id ? { ...node, name: trimmedName } : node));
      }
      toast.success(`Renamed to ${trimmedName}`);
    }

    setDialogMode(null);
  };

  const deleteSelected = async () => {
    if (!selectedNode) return;
    if (selectedNode.type === "file") {
      await onDeleteFile(selectedNode.id.replace("file:", ""));
      setSelectedId(null);
      return;
    }
    if (selectedNode.type === "folder") {
      const hasChildren = nodes.some((node) => node.parentId === selectedNode.id);
      if (hasChildren) {
        toast.error("Folder is not empty.");
        return;
      }
      setFolders((current) => current.filter((node) => node.id !== selectedNode.id));
    } else {
      setSheets((current) => current.filter((node) => node.id !== selectedNode.id));
    }
    setSelectedId(null);
    toast.success("Removed from directory");
  };

  const upload = () => inputRef.current?.click();

  const handleUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    if (selected.length) toast.info(`${selected.length} file${selected.length === 1 ? "" : "s"} selected. Backend upload integration will place them in this directory.`);
    event.target.value = "";
  };

  const openNode = (node: DirectoryNode) => {
    setSelectedId(node.id);
    if (node.type === "folder") setCurrentId(node.id);
    if (node.type === "google_sheet" && node.url) window.open(node.url, "_blank", "noopener,noreferrer");
    if (node.type === "file") {
      const file = files.find((item) => `file:${item.id}` === node.id);
      if (file) onDownload(file);
    }
  };

  return (
    <TooltipProvider>
      <section className="card-hard overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b-2 px-4 py-3">
          <div className="min-w-0 flex-1 overflow-x-auto">
            <div className="flex min-w-max items-center gap-1 text-sm">
              <button className="font-semibold hover:text-primary" onClick={() => setCurrentId(ROOT_DIRECTORY_ID)}>Files</button>
              {breadcrumb.map((node) => (
                <span key={node.id} className="flex items-center gap-1">
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  <button className="hover:text-primary" onClick={() => setCurrentId(node.id)}>{node.name}</button>
                </span>
              ))}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" onClick={createFolder}><FolderPlus /></Button></TooltipTrigger><TooltipContent>New folder</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" onClick={addSheet}><Sheet /></Button></TooltipTrigger><TooltipContent>Add Google Sheet</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><Button size="icon" onClick={upload}><Plus /></Button></TooltipTrigger><TooltipContent>Upload files</TooltipContent></Tooltip>
          </div>
        </div>

        <input ref={inputRef} type="file" multiple className="hidden" onChange={handleUpload} />

        <ContextMenu>
          <ContextMenuTrigger asChild>
            <div className="min-h-[280px] p-3" onClick={() => setSelectedId(null)}>
              {currentChildren.length === 0 ? (
                <div className="flex min-h-[250px] flex-col items-center justify-center text-center text-muted-foreground">
                  <Folder className="mb-3 h-10 w-10" />
                  <p className="font-display font-semibold text-foreground">This folder is empty</p>
                  <p className="mt-1 text-xs">Upload a file or create a folder to get started.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {currentChildren.map((node) => (
                    <ContextMenu key={node.id}>
                      <ContextMenuTrigger asChild>
                        <button
                          className={cn("group flex min-w-0 flex-col items-center gap-2 rounded-lg border-2 border-transparent p-4 text-center transition-colors hover:bg-accent/40", selectedId === node.id && "border-primary bg-accent/40")}
                          onClick={(event) => { event.stopPropagation(); setSelectedId(node.id); }}
                          onDoubleClick={() => openNode(node)}
                        >
                          {node.type === "folder" ? <Folder className="h-10 w-10" /> : node.type === "google_sheet" ? <Sheet className="h-10 w-10" /> : <File className="h-10 w-10" />}
                          <span className="w-full truncate text-sm" title={node.name}>{node.name}</span>
                        </button>
                      </ContextMenuTrigger>
                      <ContextMenuContent>
                        <ContextMenuItem onSelect={() => openNode(node)}>{node.type === "folder" ? "Open" : node.type === "google_sheet" ? "Open in Google Sheets" : "Download"}</ContextMenuItem>
                        <ContextMenuSeparator />
                        <ContextMenuItem onSelect={() => { setSelectedId(node.id); renameSelected(); }}><Pencil className="mr-2 h-4 w-4" />Rename</ContextMenuItem>
                        {node.type === "folder" && <ContextMenuItem onSelect={() => { setSelectedId(node.id); createFolder(); }}><FolderPlus className="mr-2 h-4 w-4" />Create folder</ContextMenuItem>}
                        <ContextMenuItem className="text-destructive focus:text-destructive" onSelect={() => { setSelectedId(node.id); void deleteSelected(); }}><Trash2 className="mr-2 h-4 w-4" />Delete</ContextMenuItem>
                      </ContextMenuContent>
                    </ContextMenu>
                  ))}
                </div>
              )}
            </div>
          </ContextMenuTrigger>
          <ContextMenuContent>
            <ContextMenuItem onSelect={upload}><Upload className="mr-2 h-4 w-4" />Upload files</ContextMenuItem>
            <ContextMenuItem onSelect={createFolder}><FolderPlus className="mr-2 h-4 w-4" />Create folder</ContextMenuItem>
            <ContextMenuItem onSelect={addSheet}><Sheet className="mr-2 h-4 w-4" />Add Google Sheet</ContextMenuItem>
            {selectedNode && <><ContextMenuSeparator /><ContextMenuItem onSelect={renameSelected}><Pencil className="mr-2 h-4 w-4" />Rename</ContextMenuItem><ContextMenuItem className="text-destructive focus:text-destructive" onSelect={() => void deleteSelected()}><Trash2 className="mr-2 h-4 w-4" />Delete</ContextMenuItem></>}
          </ContextMenuContent>
        </ContextMenu>

        <div className="flex items-center justify-between border-t-2 px-4 py-2 text-xs text-muted-foreground">
          <span>{currentChildren.length} item{currentChildren.length === 1 ? "" : "s"}</span>
          <MoreVertical className="h-4 w-4" />
        </div>
      </section>

      <Dialog open={dialogMode !== null} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent className="border-2">
          <DialogHeader><DialogTitle>{dialogMode === "folder" ? "Create folder" : dialogMode === "sheet" ? "Add Google Sheet" : "Rename"}</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <Input autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="Name" onKeyDown={(event) => event.key === "Enter" && submitDialog()} />
            {dialogMode === "sheet" && <Input value={sheetUrl} onChange={(event) => setSheetUrl(event.target.value)} placeholder="https://docs.google.com/spreadsheets/..." />}
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setDialogMode(null)}>Cancel</Button><Button onClick={submitDialog}>Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
}
