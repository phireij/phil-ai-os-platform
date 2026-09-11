const copy = {
  en: {
    previewStrip: "PRE-PRODUCTION PREVIEW · Visual progress only · No live orders, payments, SMS, inventory, or WooCommerce writes",
    navShop: "Shop", navOrder: "Order", navCustom: "Custom Cake", navPickup: "Quick Pickup", navCart: "Cart preview",
    heroEyebrow: "Ruby's Cake Delights · Ichikawa, Chiba",
    heroTitle: "Sweet moments, made a little more special.",
    heroCopy: "A first look at the customer-facing Ruby's Cake Delights storefront direction. This page is intentionally separated from production while the catalog, media, fulfillment rules and final launch approvals are still being completed.",
    heroPrimary: "Explore the working selection", heroSecondary: "Preview custom cake request",
    visualNote: "Brand imagery and approved product photography will replace this presentation art in later preview checkpoints.",
    catalogEyebrow: "Working catalog preview", catalogTitle: "A taste of what's taking shape",
    catalogNote: "These cards reflect the current working three-product subset only. They are not the final Initial Launch Catalog and are not published to WooCommerce.",
    workingPreview: "Working preview",
    moistDescription: "Rich chocolate cake presented here as a storefront layout preview while final media, Japanese copy and fulfillment details remain gated.",
    moistPrice: "From ¥3,500", moistVariant: "15 cm working variant",
    fudgyDescription: "A compact treat used to exercise product-card, cart and fulfillment presentation. Final temperature and packaging classification is still under review.",
    ensaymadaDescription: "A savory-sweet pastry card using the owner-confirmed working price while final packaging, media and launch approval remain pending.",
    workingPrice: "Working catalog price", ownerConfirmedPrice: "Owner-confirmed working price",
    jpNamePending: "Japanese product name remains owner-gated and is intentionally not invented in this preview.",
    servicesEyebrow: "Ordering experience", servicesTitle: "Built around how Ruby's customers order",
    servicesNote: "The visual storefront will progressively connect to the already-tested customer-flow foundations without enabling production actions early.",
    serviceShopTitle: "Shop ready-made favorites", serviceShopCopy: "Browse clear product details, availability and fulfillment guidance before entering the governed checkout path.",
    serviceCustomTitle: "Request a custom cake", serviceCustomCopy: "Choose requested date, fulfillment, cake type, reference images and add-ons through the existing mobile-first intake preview.",
    servicePickupTitle: "Quick Pickup", servicePickupCopy: "A future WooCommerce pickup experience designed to remain fail-closed until inventory, capacity and payment readiness are confirmed.",
    progressTitle: "This is a visual progress checkpoint, not a launch candidate.",
    progressCopy: "Future checkpoints will replace placeholders with approved Ruby branding, verified product media, bilingual customer copy and more production-shaped navigation as those inputs become ready.",
    authorityPill: "Production authority: unchanged",
    mobileShop: "Shop", mobileCustom: "Custom", mobilePickup: "Pickup",
    footer: "Ruby's Cake Delights · Storefront progress preview · Not indexed · Not production",
  },
  ja: {
    previewStrip: "プレプロダクション・プレビュー · 表示確認用 · 注文・決済・SMS・在庫・WooCommerce更新は実行されません",
    navShop: "商品", navOrder: "ご注文", navCustom: "オーダーケーキ", navPickup: "クイック受取", navCart: "カート確認",
    heroEyebrow: "Ruby's Cake Delights · 千葉県市川市",
    heroTitle: "大切なひとときを、もっと特別に。",
    heroCopy: "Ruby's Cake Delights のお客様向けストアデザインの進捗プレビューです。商品カタログ、画像、配送条件、最終公開承認が確定するまでは、本番サイトから分離して表示しています。",
    heroPrimary: "現在の商品プレビューを見る", heroSecondary: "オーダーケーキ受付を確認",
    visualNote: "今後のプレビューでは、承認済みのブランド素材と商品写真に置き換える予定です。",
    catalogEyebrow: "作業中カタログ", catalogTitle: "現在かたちになっている商品",
    catalogNote: "ここに表示しているのは現在の3商品だけです。初回公開カタログの最終版ではなく、WooCommerceにも公開されていません。",
    workingPreview: "作業中プレビュー",
    moistDescription: "商品ページの見え方を確認するための表示です。最終画像、日本語の商品コピー、配送詳細はまだ承認待ちです。",
    moistPrice: "¥3,500〜", moistVariant: "15cm 作業中バリエーション",
    fudgyDescription: "商品カード、カート、配送表示の確認に使用しています。温度帯と梱包区分は最終確認中です。",
    ensaymadaDescription: "オーナー確認済みの作業価格を使った表示です。梱包、商品画像、公開承認はまだ確定していません。",
    workingPrice: "作業中カタログ価格", ownerConfirmedPrice: "オーナー確認済み作業価格",
    jpNamePending: "日本語の商品名はオーナー承認待ちのため、このプレビューでは推測して追加していません。",
    servicesEyebrow: "ご注文体験", servicesTitle: "Ruby's Cake Delights のご注文方法に合わせた設計",
    servicesNote: "すでに検証済みのお客様向けフローへ段階的につなげながら、本番機能は早期に有効化しない設計です。",
    serviceShopTitle: "定番商品を選ぶ", serviceShopCopy: "商品詳細、在庫、受取・配送案内を確認してから、安全に管理されたチェックアウトへ進みます。",
    serviceCustomTitle: "オーダーケーキを相談", serviceCustomCopy: "希望日、受取・配送方法、ケーキ種類、参考画像、追加オプションをモバイル中心の受付画面から確認できます。",
    servicePickupTitle: "クイック受取", servicePickupCopy: "在庫、受取枠、決済準備が確認されるまでは有効化されない WooCommerce 受取体験の予定です。",
    progressTitle: "これはデザイン進捗の確認用であり、公開候補ではありません。",
    progressCopy: "今後、承認済みブランド素材、確認済み商品画像、日英両言語のコピー、より本番に近いナビゲーションへ段階的に更新します。",
    authorityPill: "本番権限：変更なし",
    mobileShop: "商品", mobileCustom: "オーダー", mobilePickup: "受取",
    footer: "Ruby's Cake Delights · ストア進捗プレビュー · 検索非表示 · 本番環境ではありません",
  },
};

const localeSelect = document.querySelector("#ruby-locale");

function normalizeLocale(value) {
  return value === "ja" ? "ja" : "en";
}

function applyLocale(locale) {
  const selected = normalizeLocale(locale);
  document.documentElement.lang = selected;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (copy[selected][key]) node.textContent = copy[selected][key];
  });
  localeSelect.value = selected;
  const url = new URL(location.href);
  url.searchParams.set("lang", selected);
  history.replaceState(null, "", url);
  try { localStorage.setItem("ruby_preview_locale", selected); } catch {}
}

const params = new URLSearchParams(location.search);
let initial = params.get("lang");
if (!initial) {
  try { initial = localStorage.getItem("ruby_preview_locale"); } catch {}
}
if (!initial) initial = navigator.language?.startsWith("ja") ? "ja" : "en";

applyLocale(initial);
localeSelect.addEventListener("change", () => applyLocale(localeSelect.value));
