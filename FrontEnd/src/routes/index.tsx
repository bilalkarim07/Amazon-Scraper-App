import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useRef, useState, useEffect } from "react";
import { CloudUpload, FileSpreadsheet, Loader2, Play, X, Check, AlertCircle, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { useScrape } from "../lib/scrape-store";

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

// Helper to generate default output name
const defaultOutputName = (sourceName: string) =>
  `${sourceName.replace(/\.csv$/i, "")}_scraped.csv`;

function ScrapeNew() {
  const { files, job, backendOnline, startJob, cancelJob } = useScrape();

  // File state — store both display info AND the raw File object for FormData
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

  const processing = job.status === "processing";
  const pct = job.total ? Math.round((job.done / job.total) * 100) : 0;

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

  const isValidOutputName = (name: string): boolean =>
    name.trim().length > 0 && name.trim().toLowerCase().endsWith(".csv");

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

  const threadDots = useMemo(() => [1, 2, 3, 4], []);

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

        {/* Fields */}
        <div className="mt-6 grid gap-5">
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

          {/* OUTPUT FILE NAME FIELD */}
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

        {/* Action / progress */}
        <div className="mt-8">
          {job.status === "idle" && (
            <button
              onClick={onStart}
              disabled={!backendOnline}
              className="mx-auto flex items-center gap-2 rounded-full border-2 bg-primary px-10 py-3 font-display text-lg font-bold shadow-[4px_4px_0_0_var(--ink)] press disabled:opacity-50"
            >
              <Play className="h-4 w-4" /> Start
            </button>
          )}

          {processing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between font-display text-lg">
                <span className="flex items-center gap-2 text-accent-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Processing
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
              <p className="text-xs text-muted-foreground">
                Polling for updates every 3 seconds…
              </p>
              <button
                onClick={() => {
                  cancelJob();
                  toast("Job monitoring stopped. The scraper may still be running.");
                }}
                className="rounded-lg border-2 bg-card px-4 py-2 text-xs font-semibold press"
              >
                Stop Watching
              </button>
            </div>
          )}

          {job.status === "done" && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 bg-accent/40 p-4">
              <span className="flex items-center gap-2 font-display font-semibold">
                <Check className="h-4 w-4" /> Finished {job.total} listings from{" "}
                {job.sourceName}
              </span>
              <button
                onClick={cancelJob}
                className="rounded-lg border-2 bg-primary px-4 py-2 text-xs font-semibold press"
              >
                Scrape another
              </button>
            </div>
          )}

          {job.status === "failed" && (
            <div className="flex flex-wrap items-start gap-3 rounded-xl border-2 border-destructive/40 bg-destructive/10 p-4">
              <AlertCircle className="h-5 w-5 shrink-0 text-destructive mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="font-display font-semibold text-destructive">Scraping failed</p>
                {job.error && (
                  <p className="mt-1 text-xs text-muted-foreground break-words">{job.error}</p>
                )}
              </div>
              <button
                onClick={cancelJob}
                className="rounded-lg border-2 bg-primary px-4 py-2 text-xs font-semibold press"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

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