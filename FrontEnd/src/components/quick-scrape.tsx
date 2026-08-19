import { useMemo, useState } from "react";
import { Link2, Plus, Trash2, Play, Loader2, Check, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { useScrape } from "../lib/scrape-store";
import { downloadJobOutput } from "../lib/download";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Marketplace = { label: string; domain: string; currency_code: string; currency_symbol: string };
type Props = { marketplaces: Record<string, Marketplace>; marketplace: string; currencyCode: string; currencySymbol: string; loadingMarketplaces: boolean; onMarketplaceChange: (value: string) => void };
type LinkRow = { value: string; error?: string };
const MAX = 10;

const host = (v: string) => v.toLowerCase().replace(/^www\./, "");
const validAmazonProduct = (value: string, domain: string) => {
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" && host(url.hostname) === host(domain) && /\/(?:dp|gp\/product|gp\/aw\/d)\/[A-Z0-9]{10}(?:[/?]|$)/i.test(url.pathname);
  } catch { return false; }
};
const makeCsv = (links: string[]) => new File(["\uFEFF", ["Links", ...links].join("\r\n") + "\r\n"], "quick_scrape_links.csv", { type: "text/csv;charset=utf-8" });
const uniqueName = (files: { name: string }[]) => {
  const used = new Set(files.map((f) => f.name.toLowerCase()));
  if (!used.has("quick_scrape_scraped.csv")) return "quick_scrape_scraped.csv";
  let n = 1;
  while (used.has(`quick_scrape_scraped_${n}.csv`)) n++;
  return `quick_scrape_scraped_${n}.csv`;
};

export function QuickScrape({ marketplaces, marketplace, currencyCode, currencySymbol, loadingMarketplaces, onMarketplaceChange }: Props) {
  const { files, job, backendOnline, startJob, cancelJob, resetJob } = useScrape();
  const [rows, setRows] = useState<LinkRow[]>([{ value: "" }]);
  const [open, setOpen] = useState(false);
  const [firstWait, setFirstWait] = useState("3");
  const [nextWait, setNextWait] = useState("10");
  const [keywords, setKeywords] = useState("UPC,ASIN,Model Product Information");
  const domain = marketplaces[marketplace]?.domain ?? "amazon.com";
  const processing = job.status === "processing" || job.status === "cancelling";
  const cancelling = job.status === "cancelling";
  const links = useMemo(() => rows.map((r) => r.value.trim()).filter(Boolean), [rows]);
  const pct = job.total ? Math.round(job.done / job.total * 100) : 0;

  const validate = () => {
    const next = rows.map((r) => ({ value: r.value }));
    const seen = new Set<string>(); let ok = links.length > 0 && links.length <= MAX;
    next.forEach((r) => {
      const value = r.value.trim();
      if (!value) { r.error = "Enter an Amazon product link."; ok = false; return; }
      const key = value.replace(/\/$/, "").toLowerCase();
      if (seen.has(key)) { r.error = "Duplicate product link."; ok = false; return; }
      seen.add(key);
      if (!validAmazonProduct(value, domain)) { r.error = `Use a valid ${domain} product URL.`; ok = false; }
    });
    if (links.length > MAX) toast.error(`Quick Scrape supports up to ${MAX} links.`);
    setRows(next); return ok;
  };
  const addRow = () => rows.length < MAX ? setRows((r) => [...r, { value: "" }]) : toast.info(`You can add up to ${MAX} links.`);
  const removeRow = (i: number) => setRows((r) => r.length === 1 ? [{ value: "" }] : r.filter((_, n) => n !== i));
  const changeRow = (i: number, value: string) => setRows((r) => r.map((x, n) => n === i ? { value } : x));

  const start = async () => {
    if (!backendOnline) return toast.error("Backend is offline. Start the Python server first.");
    if (!validate()) { setOpen(true); return toast.error("Fix the product links first."); }
    const fw = Number(firstWait), nw = Number(nextWait);
    if (!Number.isInteger(fw) || fw < 1 || fw > 5) return toast.error("First Page Wait must be between 1 and 5 minutes.");
    if (!Number.isInteger(nw) || nw < 3 || nw > 60) return toast.error("Next Page Wait must be between 3 and 60 seconds.");
    try {
      await startJob({ file: makeCsv(links), sourceName: "Quick Scrape", rows: links.length, column: "Links", threads: 1, outputName: uniqueName(files), firstPageWait: fw, nextPageWait: nw, keywords: keywords.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 10), marketplace, currencyCode, currencySymbol, quickScrape: true });
      toast.success("Quick Scrape started — no scraping credits were used.");
    } catch (e) { toast.error(e instanceof Error ? e.message : "Failed to start Quick Scrape."); }
  };
  const reset = () => { resetJob(); setRows([{ value: "" }]); };

  return <>
    <div className="grid gap-5">
      <div className="rounded-xl border-2 border-dashed bg-muted/40 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl border-2 bg-primary"><Link2 className="h-5 w-5" /></span><div><p className="font-display font-semibold">{links.length ? `${links.length} Amazon product link${links.length === 1 ? "" : "s"}` : "Add Amazon product page links"}</p><p className="text-xs text-muted-foreground">Add up to 10 links. Quick Scrape is credit-free.</p></div></div>
          <button onClick={() => setOpen(true)} disabled={processing} className="rounded-lg border-2 bg-primary px-4 py-2 font-mono text-xs font-semibold uppercase tracking-widest shadow-[2px_2px_0_0_var(--ink)] press disabled:opacity-50">Add Links</button>
        </div>
      </div>
      <div className="rounded-xl border-2 border-green-500/30 bg-green-500/5 p-4"><p className="font-semibold">No credits will be consumed</p><p className="mt-1 text-xs text-muted-foreground">Quick Scrape uses the existing scraper with exactly 1 worker and bypasses quota reservation and settlement.</p></div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div><label className="font-display text-sm font-semibold">Amazon Marketplace</label><Select value={marketplace} onValueChange={onMarketplaceChange} disabled={processing || loadingMarketplaces}><SelectTrigger className="mt-1 w-full rounded-lg border-2"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(marketplaces).filter(([id]) => id !== "ALL_EUROPE").map(([id, c]) => <SelectItem key={id} value={id}>{c.label} ({c.domain})</SelectItem>)}</SelectContent></Select><p className="mt-1 text-xs text-muted-foreground">Links must match this marketplace.</p></div>
        <div><label className="font-display text-sm font-semibold">Currency</label><div className="mt-1 flex h-10 items-center gap-2 rounded-lg border-2 bg-background px-3 text-sm"><span>{currencySymbol}</span><span>{currencyCode}</span></div><p className="mt-1 text-xs text-muted-foreground">Automatically set for this marketplace.</p></div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-1"><span className="font-display text-sm font-semibold">Threads</span><span className="text-xs text-muted-foreground">Fixed to 1 for Quick Scrape.</span><input value="1" readOnly className="w-24 rounded-lg border-2 bg-muted px-3 py-2 text-sm" /></label><label className="grid gap-1"><span className="font-display text-sm font-semibold">Output File</span><span className="text-xs text-muted-foreground">Generated automatically.</span><input value={uniqueName(files)} readOnly className="rounded-lg border-2 bg-muted px-3 py-2 text-sm" /></label></div>
      <div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-1"><span className="font-display text-sm font-semibold">First Page Wait</span><span className="text-xs text-muted-foreground">Minutes (1–5)</span><input type="number" min={1} max={5} value={firstWait} disabled={processing} onChange={(e) => setFirstWait(e.target.value)} className="rounded-lg border-2 bg-background px-3 py-2 text-sm" /></label><label className="grid gap-1"><span className="font-display text-sm font-semibold">Next Page Wait</span><span className="text-xs text-muted-foreground">Seconds (3–60)</span><input type="number" min={3} max={60} value={nextWait} disabled={processing} onChange={(e) => setNextWait(e.target.value)} className="rounded-lg border-2 bg-background px-3 py-2 text-sm" /></label></div>
      <label className="grid gap-1"><span className="font-display text-sm font-semibold">Keywords</span><span className="text-xs text-muted-foreground">Comma-separated, maximum 10.</span><input value={keywords} disabled={processing} onChange={(e) => setKeywords(e.target.value)} className="rounded-lg border-2 bg-background px-3 py-2 text-sm" /></label>

      {job.status === "done" || job.status === "cancelled" ? <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-6 space-y-4"><div className="flex items-center gap-3"><div className="rounded-full bg-green-500/20 p-2 text-green-600"><Check className="h-5 w-5" /></div><div><h2 className="font-display text-lg font-bold">{job.status === "done" ? "Quick Scrape finished" : "Quick Scrape cancelled"}</h2><p className="text-sm text-muted-foreground">Processed {job.done} of {job.total} product links.</p></div></div><div className="flex gap-3"><button onClick={() => job.jobId && downloadJobOutput(job.jobId)} className="rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase shadow-[2px_2px_0_0_var(--ink)] press">Download File</button><button onClick={reset} className="rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase shadow-[2px_2px_0_0_var(--ink)] press">Scrape Another</button></div><p className="text-sm text-muted-foreground">The output is also available later from the Files page.</p></div> : null}
      {job.status === "failed" ? <div className="rounded-xl border-2 border-destructive/30 bg-destructive/5 p-5"><div className="flex items-center gap-3"><AlertCircle className="h-5 w-5 text-destructive" /><p className="font-semibold">Quick Scrape failed</p></div><p className="mt-2 text-sm text-muted-foreground">{job.error}</p><button onClick={reset} className="mt-3 rounded-lg border-2 px-4 py-2 text-sm font-semibold press">Try Again</button></div> : null}
      {job.status === "idle" ? <button onClick={start} disabled={!backendOnline || links.length === 0} className="mx-auto flex items-center gap-2 rounded-full border-2 bg-primary px-10 py-3 font-display text-lg font-bold shadow-[4px_4px_0_0_var(--ink)] press disabled:opacity-50"><Play className="h-4 w-4" />Start Quick Scrape</button> : null}
      {processing ? <div className="space-y-3"><div className="flex items-center justify-between font-display text-lg"><span className="flex items-center gap-2"><Loader2 className={`h-4 w-4 ${!cancelling ? "animate-spin" : ""}`} />{cancelling ? "Cancelling..." : "Quick Scraping"}</span><span className="font-mono text-sm">{job.done}/{job.total}</span></div><div className="h-4 overflow-hidden rounded-full border-2 bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} /></div>{!cancelling && <button onClick={cancelJob} className="rounded-lg border-2 bg-destructive px-4 py-2 text-xs font-semibold text-destructive-foreground press">Cancel Scraping</button>}</div> : null}
    </div>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Add Amazon Product Links</DialogTitle><DialogDescription>Enter up to 10 {domain} product pages. Links are validated in the browser before the job starts.</DialogDescription></DialogHeader><div className="max-h-[55vh] space-y-3 overflow-y-auto pr-1">{rows.map((row, i) => <div key={i} className="grid grid-cols-[1fr_auto] gap-2"><div><input value={row.value} onChange={(e) => changeRow(i, e.target.value)} placeholder={`Amazon product link ${i + 1}`} className={`w-full rounded-lg border-2 bg-background px-3 py-2 text-sm outline-none ${row.error ? "border-destructive" : ""}`} />{row.error && <p className="mt-1 text-xs font-semibold text-destructive">{row.error}</p>}</div><button onClick={() => removeRow(i)} className="h-10 rounded-lg border-2 px-3 press" aria-label="Remove link"><Trash2 className="h-4 w-4" /></button></div>)}</div><div className="flex items-center justify-between text-xs text-muted-foreground"><span>{links.length} / {MAX} links</span><button onClick={addRow} disabled={rows.length >= MAX} className="inline-flex items-center gap-1 rounded-lg border-2 px-3 py-2 font-semibold press disabled:opacity-50"><Plus className="h-3.5 w-3.5" />Add another</button></div><DialogFooter><button onClick={() => setOpen(false)} className="rounded-lg border-2 px-4 py-2 text-sm font-semibold press">Cancel</button><button onClick={() => { if (validate()) { setOpen(false); toast.success(`${links.length} link${links.length === 1 ? "" : "s"} added.`); } }} className="rounded-lg border-2 bg-primary px-4 py-2 text-sm font-semibold shadow-[2px_2px_0_0_var(--ink)] press">Add Links</button></DialogFooter></DialogContent></Dialog>
  </>;
}
