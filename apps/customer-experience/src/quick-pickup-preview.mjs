import { externalQuickPickupUiState, validateExternalQuickPickupConfig } from "./pickup.mjs";

const copy = {
  en: {
    heroTitle: "Air Mobile Order Quick Pickup readiness",
    heroCopy: "This preview reads fixture-only readiness state. It does not publish or activate an external order link.",
    title: "Readiness status",
    pending: "Quick Pickup production URL is pending. No external order link is available yet.",
    activationPending: "Quick Pickup has an owner-confirmed URL, but validation or controlled activation is still pending.",
    ready: "Quick Pickup has passed the configured readiness gates for controlled activation.",
    open: "Open Quick Pickup",
    safetyTitle: "No external link is activated automatically",
    safetyCopy: "A production URL must be owner-confirmed, validated, and separately authorized before this preview may expose an active link. Automatic publication remains disabled.",
    technical: "Technical readiness details",
  },
  ja: {
    heroTitle: "Air モバイルオーダー・クイックピックアップ準備状況",
    heroCopy: "このプレビューはフィクスチャ専用の準備状況のみを読み取ります。外部注文リンクを公開・有効化しません。",
    title: "準備状況",
    pending: "クイックピックアップの本番URLは未確定です。現在、外部注文リンクは利用できません。",
    activationPending: "オーナー確認済みURLはありますが、検証または管理された有効化がまだ完了していません。",
    ready: "クイックピックアップは管理された有効化に必要な準備ゲートを通過しています。",
    open: "クイックピックアップを開く",
    safetyTitle: "外部リンクは自動で有効化されません",
    safetyCopy: "本番URLは、オーナー確認・検証・個別の有効化承認が完了した場合のみ表示できます。自動公開は無効のままです。",
    technical: "技術的な準備状況",
  },
};

const localeSelect = document.querySelector("#locale-select");
const output = document.querySelector("#quick-pickup-state");
let config;
let locale = new URLSearchParams(location.search).get("lang") === "ja" ? "ja" : "en";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function render() {
  document.documentElement.lang = locale;
  localeSelect.value = locale;
  document.querySelector("#hero-title").textContent = copy[locale].heroTitle;
  document.querySelector("#hero-copy").textContent = copy[locale].heroCopy;
  document.querySelector("#quick-pickup-title").textContent = copy[locale].title;
  document.querySelector("#safety-title").textContent = copy[locale].safetyTitle;
  document.querySelector("#safety-copy").textContent = copy[locale].safetyCopy;

  const state = externalQuickPickupUiState(config);
  const message = state.reason === "controlled_activation_ready"
    ? copy[locale].ready
    : state.reason === "activation_pending"
      ? copy[locale].activationPending
      : copy[locale].pending;

  output.innerHTML = `<strong>${escapeHtml(message)}</strong>`;
  if (state.available && state.href) {
    const link = document.createElement("a");
    link.className = "detail-link";
    link.href = state.href;
    link.rel = "noopener noreferrer";
    link.textContent = copy[locale].open;
    output.append(document.createElement("p")).append(link);
  }

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = copy[locale].technical;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify({
    available: state.available,
    href_exposed: Boolean(state.href),
    reason: state.reason,
    owner_confirmed: config.owner_confirmed,
    validation_complete: config.validation_complete,
    activation_authorized: config.activation_authorized,
    automatic_publication_authorized: config.automatic_publication_authorized,
  }, null, 2);
  details.append(summary, pre);
  output.append(details);
}

async function boot() {
  const response = await fetch("./fixtures/air-mobile-quick-pickup.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`quick pickup fixture failed: ${response.status}`);
  config = await response.json();
  validateExternalQuickPickupConfig(config);
  render();

  localeSelect.addEventListener("change", () => {
    locale = localeSelect.value === "ja" ? "ja" : "en";
    const url = new URL(location.href);
    url.searchParams.set("lang", locale);
    history.replaceState(null, "", url);
    render();
  });
}

boot().catch(() => {
  output.textContent = locale === "ja"
    ? "準備状況を読み込めませんでした。外部リンクは有効化されていません。"
    : "Readiness state could not be loaded. No external link has been activated.";
  output.setAttribute("role", "alert");
});
