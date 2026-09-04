export function localizedRelativeHref(href, locale) {
  if (typeof href !== "string" || !href.startsWith("./")) return href;
  const lang = locale === "ja" ? "ja" : "en";
  const hashIndex = href.indexOf("#");
  const hash = hashIndex >= 0 ? href.slice(hashIndex) : "";
  const withoutHash = hashIndex >= 0 ? href.slice(0, hashIndex) : href;
  const queryIndex = withoutHash.indexOf("?");
  const path = queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash;
  const query = queryIndex >= 0 ? withoutHash.slice(queryIndex + 1) : "";
  const params = new URLSearchParams(query);
  params.set("lang", lang);
  return `${path}?${params.toString()}${hash}`;
}

export function syncLocaleLinks(locale, root = document) {
  root.querySelectorAll('a[href^="./"]').forEach((link) => {
    const href = link.getAttribute("href");
    link.setAttribute("href", localizedRelativeHref(href, locale));
  });
}
