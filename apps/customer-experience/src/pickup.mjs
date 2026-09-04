export function validatePickupPolicy(policy) {
  if (policy?.fixture_only !== true) throw new Error("Sprint 4 pickup policy must be fixture_only");
  if (!Number.isInteger(policy.min_lead_minutes) || policy.min_lead_minutes < 0) {
    throw new TypeError("min_lead_minutes must be a non-negative integer");
  }
  if (!Number.isInteger(policy.max_advance_days) || policy.max_advance_days < 1) {
    throw new TypeError("max_advance_days must be a positive integer");
  }
  return policy;
}

export function evaluatePickupSelection(requestedPickupAt, nowIso, policy) {
  validatePickupPolicy(policy);
  if (!requestedPickupAt) {
    return Object.freeze({ valid: false, blocker: "pickup_time", reason: "missing" });
  }
  const pickupAt = Date.parse(requestedPickupAt);
  const now = Date.parse(nowIso);
  if (Number.isNaN(pickupAt) || Number.isNaN(now)) {
    return Object.freeze({ valid: false, blocker: "pickup_time", reason: "invalid_datetime" });
  }
  const min = now + policy.min_lead_minutes * 60_000;
  const max = now + policy.max_advance_days * 86_400_000;
  if (pickupAt < min) {
    return Object.freeze({ valid: false, blocker: "pickup_time", reason: "lead_time" });
  }
  if (pickupAt > max) {
    return Object.freeze({ valid: false, blocker: "pickup_time", reason: "too_far_ahead" });
  }
  return Object.freeze({ valid: true, blocker: null, reason: "accepted_by_fixture_policy" });
}

export function validateExternalQuickPickupConfig(config) {
  if (config?.fixture_only !== true) throw new Error("external quick pickup config must remain fixture_only");
  if (config.provider !== "air_mobile_order_quick_pickup") {
    throw new Error("external quick pickup provider must be air_mobile_order_quick_pickup");
  }

  for (const key of [
    "owner_confirmed",
    "validation_complete",
    "activation_authorized",
    "automatic_publication_authorized",
  ]) {
    if (typeof config[key] !== "boolean") throw new TypeError(`${key} must be boolean`);
  }

  if (config.automatic_publication_authorized !== false) {
    throw new Error("automatic quick pickup publication must remain disabled");
  }

  if (config.production_url !== null) {
    if (typeof config.production_url !== "string" || config.production_url.trim() !== config.production_url || !config.production_url) {
      throw new TypeError("production_url must be null or a non-empty trimmed string");
    }
    const parsed = new URL(config.production_url);
    if (parsed.protocol !== "https:") throw new Error("production_url must use https");
    if (parsed.username || parsed.password) throw new Error("production_url must not embed credentials");
    if (parsed.hash) throw new Error("production_url must not depend on a fragment");
  }

  if (config.production_url === null) {
    if (config.owner_confirmed || config.validation_complete || config.activation_authorized) {
      throw new Error("missing production_url must remain unconfirmed, unvalidated, and unauthorized");
    }
  }

  if (config.validation_complete && (!config.production_url || !config.owner_confirmed)) {
    throw new Error("validation_complete requires owner-confirmed production_url");
  }

  if (config.activation_authorized && (!config.production_url || !config.owner_confirmed || !config.validation_complete)) {
    throw new Error("activation_authorized requires validated owner-confirmed production_url");
  }

  return config;
}

export function externalQuickPickupUiState(config) {
  validateExternalQuickPickupConfig(config);
  const available = Boolean(
    config.production_url && config.owner_confirmed && config.validation_complete && config.activation_authorized,
  );
  return Object.freeze({
    available,
    href: available ? config.production_url : null,
    reason: available
      ? "controlled_activation_ready"
      : config.production_url
        ? "activation_pending"
        : "production_url_pending",
  });
}
