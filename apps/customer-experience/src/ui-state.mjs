export const UI_STATE_KINDS = Object.freeze(["loading", "empty", "error", "route_missing"]);

const messages = Object.freeze({
  en: Object.freeze({
    loading: Object.freeze({ title: "Loading products", message: "Preparing the local product preview." }),
    empty: Object.freeze({ title: "No products to show", message: "No fixture products are available in this preview." }),
    error: Object.freeze({ title: "Preview unavailable", message: "We could not load the product preview. Please try again.", retry_label: "Try again" }),
    route_missing: Object.freeze({ title: "Product unavailable", message: "That product is not available in this preview. The product list is shown instead." }),
  }),
  ja: Object.freeze({
    loading: Object.freeze({ title: "商品を読み込んでいます", message: "ローカルの商品プレビューを準備しています。" }),
    empty: Object.freeze({ title: "表示できる商品がありません", message: "このプレビューで利用できるフィクスチャ商品はありません。" }),
    error: Object.freeze({ title: "プレビューを利用できません", message: "商品プレビューを読み込めませんでした。もう一度お試しください。", retry_label: "再試行" }),
    route_missing: Object.freeze({ title: "商品を表示できません", message: "指定された商品はこのプレビューでは利用できません。商品一覧を表示しています。" }),
  }),
});

export function uiState(kind, locale = "en") {
  if (!UI_STATE_KINDS.includes(kind)) throw new TypeError("unsupported UI state");
  const selectedLocale = locale === "ja" ? "ja" : "en";
  const value = messages[selectedLocale][kind];
  return Object.freeze({
    kind,
    locale: selectedLocale,
    title: value.title,
    message: value.message,
    retry_label: value.retry_label || null,
    mutation_authorized: false,
  });
}
