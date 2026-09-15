import type { MetadataRoute } from "next";

// Static for now - the product landing pages themselves (motor, medical,
// etc.) are a content task, not yet built as individual routes. This
// sitemap lists what exists today and is the right shape to extend once
// those pages land, per spec §37's SEO page list.
export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://somosure.co.ke";
  const routes = ["", "/quote/motor", "/login", "/register"];

  return routes.map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: route === "" ? 1 : 0.8,
  }));
}
