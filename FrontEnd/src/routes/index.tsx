// FrontEnd/src/routes/index.tsx

import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useRef, useState, useEffect } from "react";
import { CloudUpload, FileSpreadsheet, Loader2, Play, X, Check, AlertCircle, WifiOff, Download } from "lucide-react";
import { toast } from "sonner";
import { useScrape, downloadFile } from "../lib/scrape-store";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Scrape New | Amazon Listing Scraper" },
      {
        name: "description",
        content:
          "Upload a CSV of Amazon product links, set threads and batch gap, and start scraping.",
      },
      { property: "og:title", content: "Scrape New | Amazon Listing Scraper" },
      {
        property: "og:description",
        content: "Upload a CSV of Amazon product links and start a batch scrape.",
      },
    ],
  }),
  component: ScrapeNew,
});

type Errors = Partial<
  Record<
    | "file"
    | "column"
    | "threads"
    | "gap"
    | "firstPageWait"
    | "nextPageWait"
    | "keywords"
    | "outputName",
    string | undefined
  >
>;

const defaultOutputName = (sourceName: string) =>
  `${sourceName.replace(/\.csv$/i, "")}_scraped.csv`;

const API_BASE =
  typeof window !== "undefined" && window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "http://localhost:8000";

// ---- FALLBACK marketplaces (used if backend is not ready) ----
const FALLBACK_MARKETPLACES: Record<string, any> = {
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
  ALL_EUROPE: {
    label: "All Europe",
    domain: "auto",
    currency_code: "AUTO",
    currency_symbol: "AUTO",
    is_europe_union: true,
  },
};

function ScrapeNew() {
  const { files, job, backendOnline, startJob, cancelJob, quota, refreshQuota, resetJob } = useScrape();

  // ---- Marketplace state ----
  const [marketplaces, setMarketplaces] = useState<Record<string, any>>({});
  const [loadingMarketplaces, setLoadingMarketplaces] = useState(true);
  const [marketplace, setMarketplace] = useState("US");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [currencySymbol, setCurrencySymbol] = useState("$");

  // ---- File & form state ----
  const [fileInfo, setFileInfo] = useState<{ name: string; rows: number; raw: File } | null>(null);
  const [column, setColumn] = useState("Links");
  const [threads, setThreads] = useState("3");
  const [gap, setGap] = useState("300");
  const [outputName, setOutputName] = useState("");
  const [outputTouched, setOutputTouched] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [firstPageWait, setFirstPageWait] = useState("3");
  const [nextPageWait, setNextPageWait] = useState("10");
  const [keywords, setKeywords] = useState("UPC,ASIN,Model Product Information");

  const processing = job.status === "processing" || job.status === "cancelling";
  const pct = job.total ? Math.round((job.done / job.total) * 100) : 0;
  const isCancelling = job.status === "cancelling";

  // ---- Reset form (for "Scrape Another") ----
  const resetScrapeForm = () => {
    resetJob();
    setFileInfo(null);
    setOutputName("");
    setOutputTouched(false);
    setErrors({});
    setDragging(false);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  // ---- Fetch marketplace config (with fallback) ----
  useEffect(() => {
    const fetchMarketplaces = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/marketplaces`);
        if (res.ok) {
          const data = await res.json();
          setMarketplaces(data);
          if (data.US) {
            setCurrencyCode(data.US.currency_code);
            setCurrencySymbol(data.US.currency_symbol);
          }
        } else {
          console.warn("Backend /api/marketplaces failed, using fallback");
          setMarketplaces(FALLBACK_MARKETPLACES);
          if (FALLBACK_MARKETPLACES.US) {
            setCurrencyCode(FALLBACK_MARKETPLACES.US.currency_code);
            setCurrencySymbol(FALLBACK_MARKETPLACES.US.currency_symbol);
          }
        }
      } catch (err) {
        console.error("Error fetching marketplaces, using fallback:", err);
        setMarketplaces(FALLBACK_MARKETPLACES);
        if (FALLBACK_MARKETPLACES.US) {
          setCurrencyCode(FALLBACK_MARKETPLACES.US.currency_code);
          setCurrencySymbol(FALLBACK_MARKETPLACES.US.currency_symbol);
        }
      } finally {
        setLoadingMarketplaces(false);
      }
    };
    fetchMarketplaces();
  }, []);

  // ---- Handle marketplace change ----
  const handleMarketplaceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setMarketplace(id);
    const config = marketplaces[id];
    if (config) {
      if (id === "ALL_EUROPE") {
        setCurrencyCode("AUTO");
        setCurrencySymbol("AUTO");
      } else {
        setCurrencyCode(config.currency_code);
        setCurrencySymbol(config.currency_symbol);
      }
    }
  };

  // ---- Output name auto-generation and uniqueness ----
  const getUniqueOutputName = (baseName: string): string => {
    if (!baseName) return "";
    let name = baseName.toLowerCase().endsWith(".csv") ? baseName : `${baseName}.csv`;
    const existingNames = new Set(files.map((f) => f.name));
    if (!existingNames.has(name)) return name;
    let i = 1;
    let candidate = name.replace(/\.csv$/, `_${i}.csv`);
    while (existingNames.has(candidate)) {
      i++;
      candidate = name.replace(/\.csv$/, `_${i}.csv`);
    }
    return candidate;
  };

  useEffect(() => {
    if (fileInfo && !outputTouched) {
      const base = defaultOutputName(fileInfo.name);
      const unique = getUniqueOutputName(base);
      setOutputName(unique);
    }
  }, [fileInfo, outputTouched, files]);

  const acceptFile = (f: File) => {
    if (!/\.csv$/i.test(f.name)) {
      setErrors((e) => ({ ...e, file: "Only .csv files are supported" }));
      toast.error("That file isn't a CSV");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result ?? "");
      const lines = text.split(/\r?\n/).filter(Boolean);
      const rows = Math.max(1, lines.length - 1);
      setFileInfo({ name: f.name, rows, raw: f });
      setErrors((e) => ({ ...e, file: undefined }));
      toast.success(`${f.name} loaded — ${rows} rows`);
      if (quota && rows > quota.remaining) {
        toast.warning(`This file has ${rows} rows, but only ${quota.remaining} quota rows remaining.`);
      }
    };
    reader.readAsText(f);
  };

  const validate = (): boolean => {
    const next: Errors = {};
    if (!fileInfo) next.file = "Upload a CSV file before starting";
    if (!column.trim()) next.column = "Column name is required";
    else if (column.trim().length > 64) next.column = "Column name is too long";

    const t = Number(threads);
    if (!threads.trim() || !Number.isInteger(t))
      next.threads = "Threads must be a whole number";
    else if (t < 1 || t > 4) next.threads = "Threads must be between 1 and 4";

    const g = Number(gap);
    if (!gap.trim() || Number.isNaN(g)) next.gap = "Batch gap must be a number";
    else if (g < 0) next.gap = "Batch gap cannot be negative";
    else if (g > 86400) next.gap = "Batch gap must be 86400 seconds or less";

    if (firstPageWait.trim()) {
      const fw = Number(firstPageWait);
      if (Number.isNaN(fw) || !Number.isInteger(fw)) {
        next.firstPageWait = "Must be a whole number";
      } else if (fw < 1 || fw > 5) {
        next.firstPageWait = "Must be between 1 and 5 minutes";
      }
    }

    if (nextPageWait.trim()) {
      const nw = Number(nextPageWait);
      if (Number.isNaN(nw) || !Number.isInteger(nw)) {
        next.nextPageWait = "Must be a whole number";
      } else if (nw < 3 || nw > 60) {
        next.nextPageWait = "Must be between 3 and 60 seconds";
      }
    }

    if (keywords.trim()) {
      const items = keywords.split(",").map((s) => s.trim()).filter(Boolean);
      if (items.length > 10) {
        next.keywords = "Maximum 10 keywords allowed";
      }
    }

    if (!outputName.trim()) {
      next.outputName = "Output file name is required";
    } else if (!outputName.trim().toLowerCase().endsWith(".csv")) {
      next.outputName = 'File name must end with ".csv"';
    } else {
      const existing = files.map((f) => f.name);
      if (existing.includes(outputName.trim())) {
        next.outputName = "A file with this name already exists. Please use a different name.";
      }
    }

    if (quota && fileInfo && fileInfo.rows > quota.remaining) {
      next.file = `File has ${fileInfo.rows} rows, but only ${quota.remaining} quota rows remaining.`;
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onStart = async () => {
    if (!validate()) {
      toast.error("Fix the highlighted fields first");
      return;
    }
    if (!backendOnline) {
      toast.error("Backend is offline. Start the Python server first.");
      return;
    }

    if (quota && fileInfo && fileInfo.rows > quota.remaining) {
      toast.error(`Quota exceeded. You have ${quota.remaining} rows remaining, but the file has ${fileInfo.rows} rows.`);
      return;
    }

    const keywordArray = keywords.trim()
      ? keywords.split(",").map((s) => s.trim()).filter(Boolean)
      : [];

    try {
      await startJob({
        file: fileInfo!.raw,
        sourceName: fileInfo!.name,
        rows: fileInfo!.rows,
        column: column.trim(),
        threads: Number(threads),
        outputName: outputName.trim(),
        firstPageWait: firstPageWait.trim() ? Number(firstPageWait) : undefined,
        nextPageWait: nextPageWait.trim() ? Number(nextPageWait) : undefined,
        keywords: keywordArray,
        marketplace,
        currencyCode,
        currencySymbol,
      });
      toast.success("Scraping job submitted");
    } catch (err: any) {
      if (err && err.error === "INVALID_COLUMN") {
        const availableStr = err.available_columns?.length
          ? `Available columns: ${err.available_columns.join(", ")}`
          : "No columns found.";
        setErrors((e) => ({
          ...e,
          column: `⚠️ Column "${err.requested_column}" not found in the CSV. ${availableStr}`,
        }));
        toast.error("Invalid CSV column name");
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to start scraping job");
      }
    }
  };

  const handleCancel = async () => {
    await cancelJob();
  };

  // ---- Download handler ----
  const handleDownload = async () => {
    if (!job.jobId) {
      toast.error("No job ID available for download");
      return;
    }
    try {
      const file: ScrapedFile = {
        id: job.jobId,
        name: job.outputFile ? job.outputFile.split(/[\\/]/).pop() ?? "output.csv" : "output.csv",
        createdAt: Date.now(),
        rows: job.done,
      };
      await downloadFile(file);
      toast.success("Download started");
    } catch (err) {
      toast.error("Failed to download output file");
      console.error(err);
    }
  };

  const threadDots = useMemo(() => [1, 2, 3, 4], []);

  // Determine if Start button should be disabled
  const isStartDisabled = !backendOnline || processing || (quota && quota.remaining <= 0) || (fileInfo && quota && fileInfo.rows > quota.remaining);

  const isDone = job.status === "done";
  const isCancelled = job.status === "cancelled";
  const isFailed = job.status === "failed";
  const showResult = isDone || isCancelled;

  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-10 md:py-16">
      <h1 className="title-pop text-3xl md:text-5xl">Scrape Amazon Product Listings</h1>
      <p className="mt-3 max-w-lg text-sm text-muted-foreground">
        Drop a CSV of product links, tune the crawl, and let the batches run.
      </p>

      {/* Backend status banner */}
      <div
        className={`mt-4 flex items-center gap-2 rounded-lg border-2 px-4 py-2 text-xs font-semibold transition-colors ${
          backendOnline
            ? "border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400"
            : "border-destructive/40 bg-destructive/10 text-destructive"
        }`}
      >
        {backendOnline ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <WifiOff className="h-3.5 w-3.5" />
        )}
        {backendOnline
          ? "Backend online — ready to scrape"
          : "Backend offline — start the Python server on port 8000"}
      </div>

      {/* ---- QUOTA DISPLAY ---- */}
      {quota && (
        <div className="mt-4 rounded-lg border-2 bg-muted/20 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Daily Scraping Quota
              </p>
              <p className="text-sm font-medium">
                {quota.used.toLocaleString()} / {quota.limit.toLocaleString()} used
              </p>
              <p className="text-xs text-muted-foreground">
                {quota.remaining.toLocaleString()} remaining
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">
                {new Date(quota.date).toLocaleDateString()}
              </p>
              <button
                onClick={refreshQuota}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                ↻ Refresh
              </button>
            </div>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{
                width: `${Math.min((quota.used / quota.limit) * 100, 100)}%`,
              }}
            />
          </div>
          {quota.remaining === 0 && (
            <p className="mt-2 text-xs font-semibold text-destructive">
              ⚠️ Daily quota exhausted. Please try again tomorrow.
            </p>
          )}
          {fileInfo && quota.remaining > 0 && fileInfo.rows > quota.remaining && (
            <p className="mt-2 text-xs font-semibold text-destructive">
              ⚠️ This file has {fileInfo.rows} rows, but only {quota.remaining} quota rows remaining. Please reduce the file or wait for quota reset.
            </p>
          )}
        </div>
      )}

      <section className="card-hard mt-6 p-5 md:p-7">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) acceptFile(f);
          }}
          className={`flex flex-col gap-4 rounded-xl border-2 border-dashed p-5 transition-colors sm:flex-row sm:items-center sm:justify-between ${
            dragging ? "bg-accent" : "bg-muted/40"
          } ${errors.file ? "border-destructive" : ""}`}
        >
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border-2 bg-primary">
              {fileInfo ? (
                <FileSpreadsheet className="h-5 w-5" />
              ) : (
                <CloudUpload className="h-5 w-5" />
              )}
            </span>
            <div>
              <p className="font-display text-base font-semibold">
                {fileInfo ? fileInfo.name : "Drop your CSV here to scrape listings"}
              </p>
              <p className="text-xs text-muted-foreground">
                {fileInfo ? `${fileInfo.rows} links detected` : "or click upload — .csv only"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {fileInfo && !processing && (
              <button
                onClick={() => setFileInfo(null)}
                className="rounded-lg border-2 px-2 py-2 text-xs press"
                aria-label="Remove file"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => inputRef.current?.click()}
              disabled={processing}
              className="rounded-lg border-2 bg-primary px-4 py-2 font-mono text-xs font-semibold uppercase tracking-widest shadow-[2px_2px_0_0_var(--ink)] press disabled:opacity-50"
            >
              Upload
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) acceptFile(f);
                e.target.value = "";
              }}
            />
          </div>
        </div>
        <FieldError msg={errors.file} />

        {/* ---- Result states (done / cancelled) ---- */}
        {showResult && (
          <div className="mt-6 rounded-xl border-2 border-primary/20 bg-primary/5 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-green-500/20 p-2 text-green-600">
                <Check className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-display text-lg font-bold">
                  {isDone ? "✓ Scraping finished" : "✓ Scraping cancelled"}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {isDone
                    ? `Finished ${job.total} listings from ${job.sourceName}`
                    : `Saved ${job.done} listings from ${job.sourceName}`}
                </p>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleDownload}
                className="inline-flex items-center gap-2 rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground shadow-[2px_2px_0_0_var(--ink)] transition-transform hover:-translate-y-0.5 press disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download File
              </button>
              <button
                onClick={resetScrapeForm}
                className="inline-flex items-center gap-2 rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground shadow-[2px_2px_0_0_var(--ink)] transition-transform hover:-translate-y-0.5 press"
              >
                <Play className="h-4 w-4" />
                Scrape Another
              </button>
            </div>

            {/* Files page message */}
            <p className="text-sm text-muted-foreground">
              You can access this output file later from the Files page.
            </p>
          </div>
        )}

        {/* ---- Failed state ---- */}
        {isFailed && (
          <div className="mt-6 rounded-xl border-2 border-red-500/20 bg-red-500/5 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-red-500/20 p-2 text-red-600">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-display text-lg font-bold text-red-600">Scraping failed</h2>
                {job.error && <p className="text-sm text-muted-foreground">{job.error}</p>}
              </div>
            </div>
            <button
              onClick={resetScrapeForm}
              className="inline-flex items-center gap-2 rounded-lg border-2 bg-primary px-5 py-2.5 font-mono text-xs font-semibold uppercase tracking-widest text-primary-foreground shadow-[2px_2px_0_0_var(--ink)] transition-transform hover:-translate-y-0.5 press"
            >
              <Play className="h-4 w-4" />
              Try again
            </button>
          </div>
        )}

        {/* ---- Fields (only shown when not in result or failed state) ---- */}
        {!showResult && !isFailed && (
          <div className="mt-6 grid gap-5">
            {/* Column Name */}
            <Field label="Column Name" hint="Header holding the product URLs" error={errors.column}>
              <input
                value={column}
                disabled={processing}
                onChange={(e) => {
                  setColumn(e.target.value);
                  setErrors((prev) => ({ ...prev, column: undefined }));
                }}
                placeholder="Links"
                className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
              />
            </Field>

            {/* ---- Marketplace and Currency (fixed layout) ---- */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">
                  Amazon Marketplace
                </label>
                <select
                  value={marketplace}
                  onChange={handleMarketplaceChange}
                  disabled={processing || loadingMarketplaces}
                  className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                >
                  {Object.entries(marketplaces).map(([id, config]) => (
                    <option key={id} value={id}>
                      {config.label} ({config.domain})
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-muted-foreground">Select the target region</p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">
                  Currency
                </label>
                <div className="flex items-center gap-2 rounded-lg border-2 bg-muted/40 px-3 py-2 text-sm font-medium h-[42px]">
                  <span className="text-lg">{currencySymbol}</span>
                  <span>{currencyCode}</span>
                  {marketplace === "ALL_EUROPE" && (
                    <span className="ml-auto text-xs text-muted-foreground">
                      ⓘ Auto-detected
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {marketplace === "ALL_EUROPE"
                    ? "Currency is detected from each Amazon URL."
                    : "Currency is automatically set for this marketplace."}
                </p>
              </div>
            </div>

            {/* Threads */}
            <Field label="Threads" hint="Parallel workers (1–4)" error={errors.threads}>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={threads}
                  disabled={processing}
                  onChange={(e) => setThreads(e.target.value)}
                  className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                />
                <div className="flex gap-1.5">
                  {threadDots.map((n) => (
                    <button
                      key={n}
                      disabled={processing}
                      onClick={() => setThreads(String(n))}
                      className={`h-8 w-8 rounded-lg border-2 text-xs font-bold transition-transform hover:-translate-y-0.5 disabled:opacity-60 ${
                        Number(threads) === n ? "bg-primary shadow-[2px_2px_0_0_var(--ink)]" : "bg-card"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            </Field>

            {/* Batch Gap */}
            <Field label="Batch Gap" hint="Seconds to wait between batches" error={errors.gap}>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={0}
                  value={gap}
                  disabled={processing}
                  onChange={(e) => setGap(e.target.value)}
                  className="w-32 rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                />
                <span className="text-sm text-muted-foreground">seconds</span>
              </div>
            </Field>

            {/* First Page Wait */}
            <Field
              label="First Page Wait"
              hint="Minutes (1–5) – optional"
              error={errors.firstPageWait}
            >
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={firstPageWait}
                  disabled={processing}
                  onChange={(e) => setFirstPageWait(e.target.value)}
                  className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                />
                <span className="text-sm text-muted-foreground">minutes</span>
              </div>
            </Field>

            {/* Next Page Wait */}
            <Field
              label="Next Page Wait"
              hint="Seconds (3–60) – optional"
              error={errors.nextPageWait}
            >
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={3}
                  max={60}
                  value={nextPageWait}
                  disabled={processing}
                  onChange={(e) => setNextPageWait(e.target.value)}
                  className="w-24 rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                />
                <span className="text-sm text-muted-foreground">seconds</span>
              </div>
            </Field>

            {/* Keywords */}
            <Field
              label="Keywords"
              hint="Comma-separated, max 10 – optional"
              error={errors.keywords}
            >
              <input
                value={keywords}
                disabled={processing}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="UPC,ASIN,Model Product Information"
                className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
              />
            </Field>

            {/* Output File Name */}
            <Field
              label="Output File Name"
              hint="Name of the scraped CSV file"
              error={errors.outputName}
            >
              <div className="flex items-center gap-2">
                <input
                  value={outputName}
                  disabled={processing}
                  onChange={(e) => {
                    setOutputName(e.target.value);
                    setOutputTouched(true);
                  }}
                  placeholder="my_scraped_data.csv"
                  className="w-full rounded-lg border-2 bg-background px-3 py-2 text-sm font-medium outline-none focus:shadow-[2px_2px_0_0_var(--ink)] disabled:opacity-60"
                />
                {fileInfo && !outputTouched && (
                  <button
                    type="button"
                    onClick={() => {
                      const base = defaultOutputName(fileInfo.name);
                      const unique = getUniqueOutputName(base);
                      setOutputName(unique);
                      setOutputTouched(false);
                    }}
                    className="rounded-lg border-2 px-3 py-2 text-xs press"
                  >
                    Reset
                  </button>
                )}
              </div>
            </Field>
          </div>
        )}

        {/* Action / progress */}
        <div className="mt-8">
          {job.status === "idle" && (
            <button
              onClick={onStart}
              disabled={isStartDisabled}
              className="mx-auto flex items-center gap-2 rounded-full border-2 bg-primary px-10 py-3 font-display text-lg font-bold shadow-[4px_4px_0_0_var(--ink)] press disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {quota && quota.remaining <= 0
                ? "Quota Exhausted"
                : fileInfo && quota && fileInfo.rows > quota.remaining
                ? "Exceeds Quota"
                : "Start"}
            </button>
          )}

          {processing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between font-display text-lg">
                <span className="flex items-center gap-2 text-accent-foreground">
                  <Loader2 className={`h-4 w-4 ${!isCancelling ? "animate-spin" : ""}`} />
                  {isCancelling ? "Cancelling..." : "Processing"}
                </span>
                <span className="font-mono text-sm text-muted-foreground">
                  {job.done}/{job.total}
                </span>
              </div>
              <div className="h-4 overflow-hidden rounded-full border-2 bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-200"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {pct}% complete
                </span>
                {!isCancelling && (
                  <button
                    onClick={handleCancel}
                    className="rounded-lg border-2 bg-destructive px-4 py-2 text-xs font-semibold text-destructive-foreground press"
                  >
                    Cancel Scraping
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

// ---- Helper components ----

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[10rem_1fr] sm:items-center sm:gap-4">
      <div>
        <p className="font-display text-sm font-semibold">{label}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div>
        {children}
        <FieldError msg={error} />
      </div>
    </div>
  );
}

function FieldError({ msg }: { msg?: string | undefined }) {
  if (!msg) return null;
  return <p className="mt-1 text-xs font-semibold text-destructive">{msg}</p>;
}