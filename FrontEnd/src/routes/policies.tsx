import { createFileRoute } from "@tanstack/react-router";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../components/ui/accordion";

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: "Scraping Policies | Amazon Listing Scraper" },
      {
        name: "description",
        content: "Rate limits, thread caps, data retention, and fair-use rules for scraping.",
      },
      { property: "og:title", content: "Scraping Policies | Amazon Listing Scraper" },
      {
        property: "og:description",
        content: "Rate limits, thread caps, and fair-use rules for the scraper.",
      },
    ],
  }),
  component: PoliciesPage,
});

const policies = [
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

function PoliciesPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-10 md:py-16">
      <h1 className="title-pop text-3xl md:text-5xl">Policies</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        How this scraper behaves, and the limits it enforces for you.
      </p>

      <section className="card-hard mt-8 px-5 py-2">
        <Accordion type="single" collapsible>
          {policies.map((p) => (
            <AccordionItem key={p.q} value={p.q}>
              <AccordionTrigger className="font-display text-base">{p.q}</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                {p.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </main>
  );
}
