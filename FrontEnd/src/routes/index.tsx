import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Check, ChevronLeft, ChevronRight, CloudUpload, Download, FileSpreadsheet, Loader2, Play, WifiOff, X } from "lucide-react";
import { toast } from "sonner";
import { useScrape } from "../lib/scrape-store";
import { downloadJobOutput } from "../lib/download";
import { QuickScrape } from "../components/quick-scrape";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Scrape New | Amazon Listing Scraper" },
      { name: "description", content: "Scrape Amazon product listings from CSV files or quickly test up to 10 Amazon product pages." },
      { property: "og:title", content: "Scrape New | Amazon Listing Scraper" },
      { property: "og:description", content: "Upload Amazon links or use Quick Scrape for a small credit-free test." },
    ],
  }),
  component: ScrapeNew,
});

type Errors = Partial<Record<"file" | "column" | "threads" | "gap" | "firstPageWait" | "nextPageWait" | "keywords" | "outputName", string>>;
type Marketplace = { label: string; domain: string; currency_code: string; currency_symbol: string };

const API_BASE = typeof window !== "undefined" && window.location.hostname === "127.0.0.1" ? "http://127.0.0.1:8000" : "http://localhost:8000";
const FALLBACK_MARKETPLACES: Record<string, Marketplace> = {
  US: { label: "United States", domain: "amazon.com", currency_code: "USD", currency_symbol: "$" },
  UK: { label: "United Kingdom", domain: "amazon.co.uk", currency_code: "GBP", currency_symbol: "£" },
  DE: { label: "Germany", domain: "amazon.de", currency_code: "EUR", currency_symbol: "€" },
  FR: { label: "France", domain: "amazon.fr", currency_code: "EUR", currency_symbol: "€" },
  IT: { label: "Italy", domain: "amazon.it", currency_code: "EUR", currency_symbol: "€" },
  ES: { label: "Spain", domain: "amazon.es", currency_code: "EUR", currency_symbol: "€" },
  NL: { label: "Netherlands", domain: "amazon.nl", currency_code: "EUR", currency_symbol: "€" },
  PL: { label: "Poland", domain: "amazon.pl", currency_code: "PLN", currency_symbol: "zł" },
  SE: { label: "Sweden", domain: "amazon.se", currency_code: "SEK", currency_symbol: "kr" },
  BE: { label: "Belgium", domain: "amazon.com.be", currency_code: "EUR", currency_symbol: "€" },
  IE: { label: "Ireland", domain: "amazon.ie", currency_code: "EUR", currency_symbol: "€" },
  TR: { label: "Turkey", domain: "amazon.com.tr", currency_code: "TRY", currency_symbol: "₺" },
  JP: { label: "Japan", domain: "amazon.co.jp", currency_code: "JPY", currency_symbol: "¥" },
  IN: { label: "India", domain: "amazon.in", currency_code: "INR", currency_symbol: "₹" },
  SG: { label: "Singapore", domain: "amazon.sg", currency_code: "SGD", currency_symbol: "S$" },
  AU: { label: "Australia", domain: "amazon.com.au", currency_code: "AUD", currency_symbol: "A$" },
  AE: { label: "UAE", domain: "amazon.ae", currency_code: "AED", currency_symbol: "د.إ" },
  SA: { label: "Saudi Arabia", domain: "amazon.sa", currency_code: "SAR", currency_symbol: "﷼" },
  EG: { label: "Egypt", domain: "amazon.eg", currency_code: "EGP", currency_symbol: "E£" },
  MX: { label: "Mexico", domain: "amazon.com.mx", currency_code: "MXN", currency_symbol: "Mex$" },
  BR: { label: "Brazil", domain: "amazon.com.br", currency_code: "BRL", currency_symbol: "R$" },
  CA: { label: "Canada", domain: "amazon.ca", currency_code: "CAD", currency_symbol: "C$" },
};

const defaultOutputName = (name: string) => `${name.replace(/\.csv$/i, "")}_scraped.csv`;

function ScrapeNew() {
  const { files, job, backendOnline, startJob, cancelJob, quota, refreshQuota, resetJob } = useScrape();
  const [mode, setMode] = useState<"normal" | "quick">("normal");
  const [marketplaces, setMarketplaces] = useState<Record<string, Marketplace>>({});
  const [loadingMarketplaces, setLoadingMarketplaces] = useState(true);
  const [marketplace, setMarketplace] = useState("US");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [currencySymbol, setCurrencySymbol] = useState("$");

  const [fileInfo, setFileInfo] = useState<{ name: string; rows: number; raw: File } | null>(null);
  const [column, setColumn] = useState("Links");
  const [threads, setThreads] = useState("3");
  const [gap, setGap] = useState("300");
  const [firstPageWait, setFirstPageWait] = useState("3");
  const [nextPageWait, setNextPageWait] = useState("10");
  const [keywords, setKeywords] = useState("UPC,ASIN,Model Product Information");
  const [outputName, setOutputName] = useState("");
  const [outputTouched, setOutputTouched] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const processing = job.status === "processing" || job.status === "cancelling";
  const cancelling = job.status === "cancelling";
  const pct = job.total ? Math.round(job.done / job.total * 100) : 0;

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/marketplaces`);
        const data = res.ok ? await res.json() : FALLBACK_MARKETPLACES;
        delete data.ALL_EUROPE;
        setMarketplaces(data);
        const us = data.US ?? FALLBACK_MARKETPLACES.US;
        setCurrencyCode(us.currency_code); setCurrencySymbol(us.currency_symbol);
      } catch {
        setMarketplaces(FALLBACK_MARKETPLACES);
      } finally { setLoadingMarketplaces(false); }
    };
    load();
  }, []);

  const changeMarketplace = (value: string) => {
    setMarketplace(value);
    const config = marketplaces[value];
    if (config) { setCurrencyCode(config.currency_code); setCurrencySymbol(config.currency_symbol); }
    setErrors((e) => ({ ...e, file: undefined }));
  };

  const uniqueOutput = (base: string) => {
    const used = new Set(files.map((f) => f.name.toLowerCase()));
    if (!used.has(base.toLowerCase())) return base;
    let n = 1;
    while (used.has(base.replace(/\.csv$/i, `_${n}.csv`).toLowerCase())) n++;
    return base.replace(/\.csv$/i, `_${n}.csv`);
  };

  useEffect(() => {
    if (fileInfo && !outputTouched) setOutputName(uniqueOutput(defaultOutputName(fileInfo.name)));
  }, [fileInfo, outputTouched, files]);

  const acceptFile = (file: File) => {
    if (!/\.csv$/i.test(file.name)) { setErrors((e) => ({ ...e, file: "Only .csv files are supported." })); return toast.error("That file isn't a CSV."); }
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result ?? "");
      const rows = Math.max(0, text.split(/\r?\n/).filter(Boolean).length - 1);
      if (!rows) return toast.error("The CSV contains no data rows.");
      setFileInfo({ name: file.name, rows, raw: file });
      setErrors((e) => ({ ...e, file: undefined }));
      toast.success(`${file.name} loaded — ${rows} rows`);
    };
    reader.readAsText(file);
  };

  const validate = () => {
    const next: Errors = {};
    if (!fileInfo) next.file = "Upload a CSV file before starting.";
    if (!column.trim()) next.column = "Column name is required.";
    else if (column.length > 64) next.column = "Column name is too long.";
    const t = Number(threads);
    if (!Number.isInteger(t) || t < 1 || t > 4) next.threads = "Threads must be between 1 and 4.";
    const g = Number(gap);
    if (!Number.isFinite(g) || g < 0 || g > 86400) next.gap = "Batch gap must be between 0 and 86400 seconds.";
    const fw = Number(firstPageWait), nw = Number(nextPageWait);
    if (!Number.isInteger(fw) || fw < 1 || fw > 5) next.firstPageWait = "Must be between 1 and 5 minutes.";
    if (!Number.isInteger(nw) || nw < 3 || nw > 60) next.nextPageWait = "Must be between 3 and 60 seconds.";
    if (keywords.split(",").map((x) => x.trim()).filter(Boolean).length > 10) next.keywords = "Maximum 10 keywords allowed.";
    if (!outputName.trim().toLowerCase().endsWith(".csv")) next.outputName = "File name must end with .csv.";
    else if (files.some((f) => f.name.toLowerCase() === outputName.trim().toLowerCase())) next.outputName = "A file with this name already exists.";
    if (quota && fileInfo && fileInfo.rows > quota.remaining) next.file = `File has ${fileInfo.rows} rows, but only ${quota.remaining} quota rows remain.`;
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const startNormal = async () => {
    if (!validate()) return toast.error("Fix the highlighted fields first.");
    if (!backendOnline) return toast.error("Backend is offline. Start the Python server first.");
    try {
      await startJob({ file: fileInfo!.raw, sourceName: fileInfo!.name, rows: fileInfo!.rows, column: column.trim(), threads: Number(threads), outputName: outputName.trim(), firstPageWait: Number(firstPageWait), nextPageWait: Number(nextPageWait), keywords: keywords.split(",").map((x) => x.trim()).filter(Boolean), marketplace, currencyCode, currencySymbol });
      toast.success("Scraping job submitted.");
    } catch (e: any) {
      if (e?.error === "INVALID_COLUMN") setErrors((x) => ({ ...x, column: `Column "${e.requested_column}" was not found. Available: ${(e.available_columns ?? []).join(", ")}` }));
      else toast.error(e instanceof Error ? e.message : "Failed to start scraping job.");
    }
  };

  const resetForm = () => {
    resetJob(); setFileInfo(null); setOutputName(""); setOutputTouched(false); setErrors({}); setDragging(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const showResult = job.status === "done" || job.status === "cancelled";

  return <main className="mx-auto w-full max-w-3xl px-5 py-10 md:py-16">
    <h1 className="title-pop text-3xl md:text-5xl">Scrape Amazon Product Listings</h1>
    <p className="mt-3 max-w-lg text-sm text-muted-foreground">Drop a CSV of product links, or use Quick Scrape to test product pages without consuming credits.</p>

    <div className={`mt-4 flex items-center gap-2 rounded-lg border-2 px-4 py-2 text-xs font-semibold ${backendOnline ? "border-green-500/40 bg-green-500/10 text-green-700" : "border-destructive/40 bg-destructive/10 text-destructive"}`}>
      {backendOnline ? <Check className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      {backendOnline ? "Backend online — ready to scrape" : "Backend offline — start the Python server on port 8000"}
    </div>

    {quota && <div className="mt-4 rounded-lg border-2 bg-muted/20 p-4"><div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Daily Scraping Quota</p><p className="text-sm font-medium">{quota.used.toLocaleString()} / {quota.limit.toLocaleString()} used</p><p className="text-xs text-muted-foreground">{quota.remaining.toLocaleString()} remaining</p></div><button onClick={refreshQuota} className="text-xs text-muted-foreground hover:text-foreground">↻ Refresh</button></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(quota.used / quota.limit * 100, 100)}%` }} /></div></div>}

    <div className="mt-6 flex items-center justify-between rounded-xl border-2 bg-card p-2 shadow-[2px_2px_0_0_var(--ink)]">
      <button onClick={() => setMode("normal")} disabled={processing} className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-bold transition ${mode === "normal" ? "bg-primary" : "opacity-60 hover:opacity-100"}`}><ChevronLeft className="h-4 w-4" />CSV Scrape</button>
      <div className="px-3 text-center"><p className="font-display text-sm font-bold">{mode === "normal" ? "Standard Scrape" : "Quick Scrape"}</p><p className="text-[10px] uppercase tracking-widest text-muted-foreground">{mode === "normal" ? "CSV workflow" : "Up to 10 · credit-free"}</p></div>
      <button onClick={() => setMode("quick")} disabled={processing} className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-bold transition ${mode === "quick" ? "bg-primary" : "opacity-60 hover:opacity-100"}`}>Quick Scrape<ChevronRight className="h-4 w-4" /></button>
    </div>

    <section className="card-hard mt-4 p-5 md:p-7">
      {mode === "quick" ? <QuickScrape marketplaces={marketplaces} marketplace={marketplace} currencyCode={currencyCode} currencySymbol={currencySymbol} loadingMarketplaces={loadingMarketplaces} onMarketplaceChange={changeMarketplace} /> : <>
        <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) acceptFile(f); }} className={`flex flex-col gap-4 rounded-xl border-2 border-dashed p-5 sm:flex-row sm:items-center sm:justify-between ${dragging ? "bg-accent" : "bg-muted/40"} ${errors.file ? "border-destructive" : ""}`}>
          <div className="flex items-center gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border-2 bg-primary">{fileInfo ? <FileSpreadsheet className="h-5 w-5" /> : <CloudUpload className="h-5 w-5" />}</span><div><p className="font-display font-semibold">{fileInfo ? fileInfo.name : "Drop your CSV here to scrape listings"}</p><p className="text-xs text-muted-foreground">{fileInfo ? `${fileInfo.rows} links detected` : "or click upload — .csv only"}</p></div></div>
          <div className="flex items-center gap-2">{fileInfo && !processing && <button onClick={() => setFileInfo(null)} className="rounded-lg border-2 px-2 py-2 press" aria-label="Remove file"><X className="h-3.5 w-3.5" /></button>}<button onClick={() => inputRef.current?.click()} disabled={processing} className="rounded-lg border-2 bg-primary px-4 py-2 font-mono text-xs font-semibold uppercase tracking-widest shadow-[2px_2px_0_0_var(--ink)] press">Upload</button><input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) acceptFile(f); e.target.value = ""; }} /></div>
        </div><FieldError msg={errors.file} />

        {showResult && <div className="mt-6 rounded-xl border-2 border-primary/20 bg-primary/5 p-6 space-y-4"><div className="flex items-center gap-3"><Check className="h-5 w-5 text-green-600" /><div><h2 className="font-display text-lg font-bold">{job.status === "done" ? "Scraping finished" : "Scraping cancelled"}</h2><p className="text-sm text-muted-foreground">Processed {job.done} of {job.total} listings.</p></div></div><div className="flex gap-3"><button onClick={() => job.jobId && downloadJobOutput(job.jobId)} className="inline-flex items-center gap-2 rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase shadow-[2px_2px_0_0_var(--ink)] press"><Download className="h-4 w-4" />Download File</button><button onClick={resetForm} className="rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase shadow-[2px_2px_0_0_var(--ink)] press">Scrape Another</button></div><p className="text-sm text-muted-foreground">You can access this output later from the Files page.</p></div>}
        {job.status === "failed" && <div className="mt-6 rounded-xl border-2 border-destructive/30 bg-destructive/5 p-5"><div className="flex items-center gap-3"><AlertCircle className="h-5 w-5 text-destructive" /><p className="font-semibold">Scraping failed</p></div><p className="mt-2 text-sm text-muted-foreground">{job.error}</p></div>}

        {!showResult && job.status !== "failed" && <div className="mt-6 grid gap-5">
          <Field label="Column Name" hint="Header holding the product URLs" error={errors.column}><input value={column} disabled={processing} onChange={(e) => setColumn(e.target.value)} className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm" /></Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><Field label="Amazon Marketplace" hint="Select the target region"><Select value={marketplace} onValueChange={changeMarketplace} disabled={processing || loadingMarketplaces}><SelectTrigger className="w-full rounded-lg border-2"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(marketplaces).map(([id, c]) => <SelectItem key={id} value={id}>{c.label} ({c.domain})</SelectItem>)}</SelectContent></Select></Field><Field label="Currency" hint="Automatically set"><div className="flex h-10 items-center gap-2 rounded-lg border-2 bg-background px-3 text-sm"><span>{currencySymbol}</span><span>{currencyCode}</span></div></Field></div>
          <Field label="Threads" hint="Parallel workers (1–4)" error={errors.threads}><div className="flex items-center gap-3"><input type="number" min={1} max={4} value={threads} disabled={processing} onChange={(e) => setThreads(e.target.value)} className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm" />{[1,2,3,4].map((n) => <button key={n} onClick={() => setThreads(String(n))} disabled={processing} className={`h-8 w-8 rounded-lg border-2 text-xs font-bold ${Number(threads) === n ? "bg-primary" : "bg-card"}`}>{n}</button>)}</div></Field>
          <Field label="Batch Gap" hint="Seconds between batches" error={errors.gap}><div className="flex items-center gap-2"><input type="number" min={0} value={gap} disabled={processing} onChange={(e) => setGap(e.target.value)} className="w-32 rounded-lg border-2 bg-background px-3 py-2 text-sm" /><span className="text-sm text-muted-foreground">seconds</span></div></Field>
          <Field label="First Page Wait" hint="Minutes (1–5)" error={errors.firstPageWait}><div className="flex items-center gap-2"><input type="number" min={1} max={5} value={firstPageWait} disabled={processing} onChange={(e) => setFirstPageWait(e.target.value)} className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm" /><span className="text-sm text-muted-foreground">minutes</span></div></Field>
          <Field label="Next Page Wait" hint="Seconds (3–60)" error={errors.nextPageWait}><div className="flex items-center gap-2"><input type="number" min={3} max={60} value={nextPageWait} disabled={processing} onChange={(e) => setNextPageWait(e.target.value)} className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm" /><span className="text-sm text-muted-foreground">seconds</span></div></Field>
          <Field label="Keywords" hint="Comma-separated, max 10" error={errors.keywords}><input value={keywords} disabled={processing} onChange={(e) => setKeywords(e.target.value)} className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm" /></Field>
          <Field label="Output File Name" hint="Name of the scraped CSV" error={errors.outputName}><input value={outputName} disabled={processing} onChange={(e) => { setOutputName(e.target.value); setOutputTouched(true); }} className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm" /></Field>
        </div>}

        {job.status === "idle" && <button onClick={startNormal} disabled={!backendOnline || processing || (quota ? quota.remaining <= 0 : false)} className="mx-auto mt-8 flex items-center gap-2 rounded-full border-2 bg-primary px-10 py-3 font-display text-lg font-bold shadow-[4px_4px_0_0_var(--ink)] press disabled:opacity-50"><Play className="h-4 w-4" />Start</button>}
        {processing && <div className="mt-8 space-y-3"><div className="flex items-center justify-between font-display text-lg"><span className="flex items-center gap-2"><Loader2 className={`h-4 w-4 ${!cancelling ? "animate-spin" : ""}`} />{cancelling ? "Cancelling..." : "Processing"}</span><span className="font-mono text-sm">{job.done}/{job.total}</span></div><div className="h-4 overflow-hidden rounded-full border-2 bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} /></div>{!cancelling && <button onClick={cancelJob} className="rounded-lg border-2 bg-destructive px-4 py-2 text-xs font-semibold text-destructive-foreground press">Cancel Scraping</button>}</div>}
      </>}
    </section>
  </main>;
}

function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return <div className="grid gap-1.5 sm:grid-cols-[10rem_1fr] sm:items-center sm:gap-4"><div><p className="font-display text-sm font-semibold">{label}</p>{hint && <p className="text-xs text-muted-foreground">{hint}</p>}</div><div>{children}<FieldError msg={error} /></div></div>;
}
function FieldError({ msg }: { msg?: string }) { return msg ? <p className="mt-1 text-xs font-semibold text-destructive">{msg}</p> : null; }
