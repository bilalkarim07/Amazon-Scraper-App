// FrontEnd/src/lib/scrape-context.ts
import { createContext, useContext } from "react";
import type { ScrapedFile, JobState, QuotaState } from "./scrape-store";

export type Ctx = {
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
  deleteFile: (id: string) => Promise<void>;
  downloadFile: (file: ScrapedFile) => Promise<void>;
  refreshFiles: () => Promise<void>;
  refreshQuota: () => Promise<void>;
  resetJob: () => void;
};

export const ScrapeContext = createContext<Ctx | null>(null);

export function useScrape() {
  const ctx = useContext(ScrapeContext);
  if (!ctx) throw new Error("useScrape must be used inside ScrapeProvider");
  return ctx;
}