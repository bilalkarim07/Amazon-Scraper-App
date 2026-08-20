import { createFileRoute } from "@tanstack/react-router";
import { HelpCircle, ShieldCheck, Check, X } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../components/ui/accordion";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../components/ui/tooltip";

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: "Policies & Compliance | Amazon Listing Scraper" },
      {
        name: "description",
        content:
          "Comprehensive policies, Amazon compliance, and usage guidelines for our Amazon Scraper tool.",
      },
      {
        property: "og:title",
        content: "Policies & Compliance | Amazon Listing Scraper",
      },
      {
        property: "og:description",
        content:
          "Learn about our policies, compliance with Amazon, and how we respect your data.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: PoliciesPage,
});

const technicalPolicies = [
  {
    q: "Thread limits",
    a: "Threads are capped between 1 and 4. Anything outside that range is rejected before a job starts, so the crawler never hammers a listing endpoint.",
  },
  {
    q: "Batch gap",
    a: "The default gap is 300 seconds between batches. Lower values increase throughput but also the chance of throttling or captchas.",
  },
  {
    q: "Input format",
    a: "Upload a .csv with one column of product URLs. The column name defaults to 'Links' and must match a header in your file.",
  },
  {
    q: "Data retention",
    a: "Scraped exports stay in this app until you delete them. Deleting a file removes both the export and its metadata.",
  },
  {
    q: "Fair use",
    a: "Only collect publicly visible listing data, respect robots directives, and don't resell raw scraped content.",
  },
];

const complianceDetails = [
  {
    q: "What is this software designed to do?",
    a: "This software was created to simplify and automate the process of extracting product information from Amazon for sellers. Instead of manually browsing and copying product data or paying expensive monthly subscription fees for tools you might not fully utilize, our Amazon Product Scraper allows you to extract bulk product information in one simple operation. You pay once, not recurring monthly charges.",
  },
  {
    q: "How does this software respect Amazon's policies?",
    a: "We take Amazon's policies very seriously. This software does NOT have Amazon's direct or indirect endorsement. We've deliberately designed it with performance limitations to ensure respectful scraping practices. The tool only extracts publicly available information that anyone can see when browsing Amazon.com. It specifically excludes private seller data, shop information, and any protected content.",
  },
  {
    q: "What data can this software scrape?",
    a: "Our scraper only collects publicly visible information such as product titles, prices, descriptions, ratings, and reviews that are already displayed on Amazon product pages. We do NOT access private information including private seller shop details, customer personal information, or any data hidden behind login restrictions.",
  },
  {
    q: "Performance and Rate Limiting",
    a: "By design, this software has intentional performance limitations. We use rate limiting and batch gaps to ensure we don't overload Amazon's servers. This means scraping takes longer than some alternatives, but that's intentional—it shows our commitment to responsible scraping that respects Amazon's infrastructure.",
  },
];

const glossary = [
  {
    term: "Threads",
    def: "These are like workers that collect data simultaneously. We limit them to 1-4 to prevent overwhelming Amazon's servers and getting blocked.",
  },
  {
    term: "Batch Gap",
    def: "The waiting time between each batch of requests. Longer gaps are safer but slower. 300 seconds (5 minutes) is our default safe setting.",
  },
  {
    term: "Rate Limiting",
    def: "A system that controls how fast we make requests to Amazon. It prevents us from asking for too much data too quickly, which could get our tool blocked.",
  },
  {
    term: "CSV File",
    def: "A simple text file (Comma Separated Values) that you can create in Excel. Each row contains one product URL you want to scrape.",
  },
  {
    term: "Public Data",
    def: "Information that anyone can see by visiting Amazon.com without logging in. This includes product prices, titles, descriptions, and reviews.",
  },
  {
    term: "Throttling",
    def: "When a server temporarily blocks or slows down requests from an IP address because it detects too many requests. We try to prevent this with our rate limiting.",
  },
];

const withoutAutomation = [
  "Hours of manual browsing and copying data",
  "Subscription to expensive third-party tools (often $50-300/month)",
  "Ongoing monthly payments even if you only use the tool occasionally",
];

const commitments = [
  "Not overloading Amazon's servers",
  "Reducing the chance of getting blocked",
  "Respecting robots.txt files and scraping guidelines",
  "Maintaining ethical scraping practices",
];

const doScrape = [
  "Product titles and descriptions",
  "Prices status",
  "Star ratings and review counts",
  "Product images (public URLs)",
  "Basic product specifications",
];

const dontScrape = [
  "Private seller shop information or metrics",
  "Customer personal information or emails",
  "Seller contact details or private messages",
  "Password-protected or login-required content",
  "Any data hidden behind authentication",
  "Private seller performance data",
];

const summary = [
  {
    label: "What you get",
    text: "Simple, affordable tool to extract Amazon product data in bulk without expensive subscriptions",
  },
  {
    label: "How it works",
    text: "Respectfully and responsibly, with intentional limits to avoid overloading servers",
  },
  {
    label: "What it scrapes",
    text: "Only public information anyone can see on Amazon.com",
  },
  {
    label: "What it doesn't scrape",
    text: "Private data, seller information, or anything behind login walls",
  },
  {
    label: "Amazon compliance",
    text: "We operate independently and have built-in limitations to show respect for Amazon's infrastructure",
  },
];

function PoliciesPage() {
  return (
    <TooltipProvider delayDuration={150}>
      <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-5 sm:py-12 md:py-16">
        <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:flex sm:justify-between">
          <div className="min-w-0">
            <h1 className="title-pop text-3xl sm:text-4xl md:text-5xl">
              Policies &amp; Compliance
            </h1>

            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Everything you need to know about how our scraper works and how
              we respect Amazon's policies.
            </p>
          </div>

          <div className="grid size-12 shrink-0 place-items-center rounded-2xl border-2 border-border bg-primary text-primary-foreground">
            <ShieldCheck className="size-6" />
          </div>
        </header>

        <section className="card-hard mt-6 p-4 sm:p-5">
          <h2 className="font-display text-base sm:text-lg">Disclaimer</h2>

          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            This is not an official product of Amazon. This software is not
            developed by Amazon or any Amazon employer or employee. It is an
            independent product and is not affiliated with, endorsed by,
            sponsored by, or otherwise officially connected with Amazon.
          </p>
        </section>

        <section className="card-hard mt-8 p-4 sm:p-6">
          <h2 className="font-display text-lg sm:text-xl">
            Why This Software Exists
          </h2>

          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Our Amazon Product Scraper was built to simplify the process of
            extracting product data in bulk. Amazon sellers often need to
            gather product information across many listings for competitive
            analysis, inventory management, or market research.
          </p>

          <p className="mt-4 text-sm font-medium">
            Without automation, this task requires:
          </p>

          <ul className="mt-2 space-y-2">
            {withoutAutomation.map((item) => (
              <li
                key={item}
                className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
              >
                <X className="mt-0.5 size-4 shrink-0 text-destructive" />
                <span className="min-w-0">{item}</span>
              </li>
            ))}
          </ul>

          <p className="mt-4 rounded-xl border-2 border-border bg-secondary p-3 text-sm leading-relaxed">
            Our solution: One-time purchase, unlimited use. No recurring fees.
            No subscriptions. Just straight-forward data extraction.
          </p>
        </section>

        <section className="card-hard mt-8 p-4 sm:p-6">
          <h2 className="font-display text-lg sm:text-xl">
            Amazon Compliance &amp; Respect
          </h2>

          <div className="mt-3 rounded-xl border-2 border-dashed border-border bg-secondary p-3">
            <p className="font-display text-sm">Important Notice</p>

            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              This software is not endorsed by Amazon, directly or indirectly.
              We operate independently and take full responsibility for how
              our tool functions.
            </p>
          </div>

          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            To demonstrate our respect for Amazon's infrastructure and
            policies, we have intentionally built performance limitations into
            our scraper. While other tools prioritize speed, we prioritize
            responsibility.
          </p>

          <p className="mt-4 text-sm font-medium">
            Our tool works more slowly than alternatives specifically because we
            are committed to:
          </p>

          <ul className="mt-2 space-y-2">
            {commitments.map((item) => (
              <li
                key={item}
                className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
              >
                <Check className="mt-0.5 size-4 shrink-0 text-success" />
                <span className="min-w-0">{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="card-hard p-4 sm:p-5">
            <h2 className="font-display text-base sm:text-lg">
              What We DO Scrape (Public Data Only)
            </h2>

            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Our scraper collects only publicly visible information:
            </p>

            <ul className="mt-3 space-y-2">
              {doScrape.map((item) => (
                <li
                  key={item}
                  className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
                >
                  <Check className="mt-0.5 size-4 shrink-0 text-success" />
                  <span className="min-w-0">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="card-hard p-4 sm:p-5">
            <h2 className="font-display text-base sm:text-lg">
              What We DO NOT Scrape (Protected Data)
            </h2>

            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Our scraper specifically excludes private and protected
              information:
            </p>

            <ul className="mt-3 space-y-2">
              {dontScrape.map((item) => (
                <li
                  key={item}
                  className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
                >
                  <X className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <span className="min-w-0">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-display text-lg sm:text-xl">
            Technical Policies
          </h2>

          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            These are the rules and limits we enforce to keep your scraping
            safe and effective.
          </p>

          <div className="card-hard mt-4 px-4 py-1 sm:px-5 sm:py-2">
            <Accordion type="single" collapsible>
              {technicalPolicies.map((p) => (
                <AccordionItem key={p.q} value={p.q}>
                  <AccordionTrigger className="text-left font-display text-sm sm:text-base">
                    {p.q}
                  </AccordionTrigger>

                  <AccordionContent className="text-sm leading-relaxed text-muted-foreground">
                    {p.a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-display text-lg sm:text-xl">
            Amazon Compliance Details
          </h2>

          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Learn how we ensure responsible scraping while respecting Amazon's
            policies.
          </p>

          <div className="card-hard mt-4 px-4 py-1 sm:px-5 sm:py-2">
            <Accordion type="single" collapsible>
              {complianceDetails.map((p) => (
                <AccordionItem key={p.q} value={p.q}>
                  <AccordionTrigger className="text-left font-display text-sm sm:text-base">
                    {p.q}
                  </AccordionTrigger>

                  <AccordionContent className="text-sm leading-relaxed text-muted-foreground">
                    {p.a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </section>

        <section className="mt-10">
          <h2 className="font-display text-lg sm:text-xl">Glossary</h2>

          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Don't worry if some technical terms seem confusing. Here's what
            they actually mean in simple language.
          </p>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {glossary.map((g) => (
              <div key={g.term} className="card-hard p-3 sm:p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 rounded-md border-2 border-border bg-secondary px-2 py-0.5 font-display text-xs sm:text-sm">
                    {g.term}
                  </span>

                  <Tooltip>
                    <TooltipTrigger
                      aria-label={`What does ${g.term} mean?`}
                      className="shrink-0 rounded-full text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <HelpCircle className="size-4" />
                    </TooltipTrigger>

                    <TooltipContent className="max-w-[16rem] text-xs leading-relaxed">
                      {g.def}
                    </TooltipContent>
                  </Tooltip>
                </div>

                <p className="mt-2 text-xs leading-relaxed text-muted-foreground sm:text-sm">
                  {g.def}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="card-hard mt-10 p-4 sm:p-6">
          <h2 className="font-display text-lg sm:text-xl">Quick Summary</h2>

          <dl className="mt-3 space-y-3">
            {summary.map((s) => (
              <div
                key={s.label}
                className="grid gap-1 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-3"
              >
                <dt className="font-display text-sm">{s.label}:</dt>

                <dd className="min-w-0 text-sm leading-relaxed text-muted-foreground">
                  {s.text}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </main>
    </TooltipProvider>
  );
}