export const QUICK_PICKUP_ROUTE_COPY = Object.freeze({
  en: Object.freeze({
    language: "Language",
    status: "Isolated route · Ordering disabled",
    hero: "Quick Pickup route foundation",
    heroCopy: "This route is implemented for controlled testing only. It cannot reserve stock, book a pickup slot, create an order, or execute payment.",
    routeTitle: "Customer ordering is not available",
    routePending: "The route exists, but activation and independent readiness gates are still pending.",
    routeDisabled: "The operator disable control is engaged. No customer order path is available.",
    fixtureTitle: "No live inventory or reservation",
    fixtureAvailable: "Historical fixture data passes the synthetic stock and slot demonstration.",
    fixtureBlocked: "Historical fixture data is blocked by the synthetic stock or slot demonstration.",
    fixtureSafety: "Synthetic data only. This result does not hold stock, reserve capacity, create an order, authorize payment, or publish this route.",
    shop: "Shop",
    cart: "Cart",
    pickup: "Pickup status",
    nav: "Quick Pickup route navigation",
    footer: "Pre-production route foundation · No customer order action",
    loadFailure: "Route state could not be loaded. Ordering remains disabled.",
  }),
  ja: Object.freeze({
    language: "言語",
    status: "分離ルート · 注文無効",
    hero: "クイックピックアップ・ルート基盤",
    heroCopy: "このルートは管理されたテスト用に実装されています。在庫確保、受取枠予約、注文作成、決済実行はできません。",
    routeTitle: "お客様の注文はまだ利用できません",
    routePending: "ルートは存在しますが、有効化と独立した準備ゲートは未完了です。",
    routeDisabled: "運用者の無効化コントロールが有効です。お客様の注文導線は利用できません。",
    fixtureTitle: "実在庫・予約ではありません",
    fixtureAvailable: "過去のフィクスチャデータは合成在庫・受取枠デモの条件を満たしています。",
    fixtureBlocked: "過去のフィクスチャデータは合成在庫または受取枠デモにより停止されています。",
    fixtureSafety: "合成データのみです。在庫確保、受取枠予約、注文作成、決済承認、ルート公開は行いません。",
    shop: "商品",
    cart: "カート",
    pickup: "受取状況",
    nav: "クイックピックアップ・ルート・ナビゲーション",
    footer: "本番前ルート基盤 · お客様の注文操作なし",
    loadFailure: "ルート状態を読み込めませんでした。注文は無効のままです。",
  }),
});

export function validateQuickPickupRouteCopy(copy = QUICK_PICKUP_ROUTE_COPY) {
  if (!copy || typeof copy !== "object") throw new TypeError("Quick Pickup copy must be an object");
  const locales = Object.keys(copy).sort();
  if (locales.join(",") !== "en,ja") throw new Error("Quick Pickup copy must contain exactly en and ja locales");

  const englishKeys = Object.keys(copy.en).sort();
  const japaneseKeys = Object.keys(copy.ja).sort();
  if (englishKeys.length === 0 || englishKeys.join("|") !== japaneseKeys.join("|")) {
    throw new Error("Quick Pickup bilingual copy keys must match exactly");
  }

  for (const locale of locales) {
    for (const key of englishKeys) {
      const value = copy[locale][key];
      if (typeof value !== "string" || value.trim().length === 0) {
        throw new Error(`Quick Pickup copy ${locale}.${key} must be a non-empty string`);
      }
    }
  }
  return copy;
}

export function quickPickupRouteCopy(locale) {
  validateQuickPickupRouteCopy();
  return QUICK_PICKUP_ROUTE_COPY[locale === "ja" ? "ja" : "en"];
}
