export type DirectoryNodeType = "folder" | "file" | "google_sheet";

export interface DirectoryNode {
  id: string;
  parentId: string | null;
  name: string;
  type: DirectoryNodeType;
  url?: string;
  size?: number;
  rows?: number;
  createdAt: number;
}

export const ROOT_DIRECTORY_ID = "root";

export function isGoogleSheetUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" && url.hostname === "docs.google.com" && url.pathname.startsWith("/spreadsheets/");
  } catch {
    return false;
  }
}

export function childrenOf(nodes: DirectoryNode[], parentId: string | null): DirectoryNode[] {
  return nodes
    .filter((node) => node.parentId === parentId)
    .sort((a, b) => {
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (a.type !== "folder" && b.type === "folder") return 1;
      return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
    });
}
