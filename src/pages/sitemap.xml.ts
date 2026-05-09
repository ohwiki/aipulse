import { CATEGORY_ORDER } from "@/lib/categories";
import { getDailyDates } from "@/lib/content";

const STATIC_PATHS = [
  "/",
  "/archive",
  "/about",
  "/privacy",
  "/contact",
  "/methodology",
  "/sources-and-attribution"
];

export async function GET(context: { site: URL | undefined }) {
  const site = context.site ?? new URL("https://pulse.ouraihub.com");
  const dailyDates = await getDailyDates();

  const urls = [
    ...STATIC_PATHS.map((pathname) => new URL(pathname, site).toString()),
    ...CATEGORY_ORDER.map((slug) => new URL(`/category/${slug}`, site).toString()),
    ...dailyDates.map((date) => new URL(`/archive/${date}`, site).toString())
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (url) => `  <url>
    <loc>${url}</loc>
  </url>`
  )
  .join("\n")}
</urlset>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8"
    }
  });
}
