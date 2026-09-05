const copy = Object.freeze({
  en: Object.freeze({
    skip: "Skip to content",
    language: "Language",
  }),
  ja: Object.freeze({
    skip: "メインコンテンツへ移動",
    language: "言語",
  }),
});

function normalizeLocale(locale) {
  return locale === "ja" ? "ja" : "en";
}

export function applyPageChromeLocale(locale = document.documentElement.lang) {
  const lang = normalizeLocale(locale);
  const localized = copy[lang];
  const skipLink = document.querySelector(".skip-link");
  const languageLabel = document.querySelector('.locale-label[for="locale-select"]');
  const localeSelect = document.querySelector("#locale-select");

  if (skipLink) skipLink.textContent = localized.skip;
  if (languageLabel) languageLabel.textContent = localized.language;
  if (localeSelect) localeSelect.setAttribute("aria-label", localized.language);
}

const localeSelect = document.querySelector("#locale-select");
localeSelect?.addEventListener("change", () => {
  queueMicrotask(() => applyPageChromeLocale(localeSelect.value));
});

new MutationObserver(() => applyPageChromeLocale(document.documentElement.lang)).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["lang"],
});

applyPageChromeLocale();
