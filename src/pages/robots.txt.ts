export async function GET(context: { site: URL | undefined }) {
  const site = context.site ?? new URL("https://pulse.ouraihub.com");
  const body = `User-agent: *
Allow: /

Sitemap: ${new URL("/sitemap.xml", site).toString()}
`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8"
    }
  });
}
