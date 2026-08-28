import type { AeoAcademyProfile, AeoArticle } from "./types";

export function buildJsonLd(academy: AeoAcademyProfile, article: AeoArticle): Record<string, unknown> {
  const orgId = academy.url
    ? `${academy.url.replace(/\/$/, "")}/#organization`
    : "#organization";

  const org: Record<string, unknown> = {
    "@type": ["LocalBusiness", "EducationalOrganization"],
    "@id": orgId,
    name: academy.name,
    description: [
      academy.location,
      academy.name,
      academy.services.length ? `주요 과정: ${academy.services.join(", ")}` : "",
      academy.evidence,
    ]
      .filter(Boolean)
      .join(". ")
      .trim(),
    url: academy.url || undefined,
    telephone: academy.phone || undefined,
    priceRange: academy.priceRange || undefined,
    openingHours: academy.openingHours || undefined,
    areaServed: academy.location || undefined,
    knowsAbout: academy.services,
  };

  if (academy.address) {
    const parts = academy.address.split(/\s+/);
    org.address = {
      "@type": "PostalAddress",
      streetAddress: academy.address,
      addressLocality: parts.find((p) => p.endsWith("구") || p.endsWith("시")) || parts[1] || "",
      addressRegion: parts[0] || "",
      addressCountry: "KR",
    };
  }

  if (academy.geoLat != null && academy.geoLng != null && !Number.isNaN(academy.geoLat)) {
    org.geo = {
      "@type": "GeoCoordinates",
      latitude: academy.geoLat,
      longitude: academy.geoLng,
    };
  }

  const graph: Record<string, unknown>[] = [
    Object.fromEntries(Object.entries(org).filter(([, v]) => v !== undefined)),
  ];

  graph.push({
    "@type": "BlogPosting",
    headline: article.title,
    description: article.metaDescription,
    articleBody: article.oneSentenceAnswer,
    keywords: article.keywords.join(", ") || undefined,
    inLanguage: "ko-KR",
    author: { "@id": orgId },
    publisher: { "@id": orgId },
    about: { "@id": orgId },
  });

  if (article.faq.length) {
    graph.push({
      "@type": "FAQPage",
      mainEntity: article.faq.map((item) => ({
        "@type": "Question",
        name: item.question,
        acceptedAnswer: { "@type": "Answer", text: item.answer },
      })),
    });
  }

  return { "@context": "https://schema.org", "@graph": graph };
}
