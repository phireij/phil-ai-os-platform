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

export function validateFirstPartyQuickPickupConfig(config) {
  if (config?.fixture_only !== true) throw new Error("first-party quick pickup config must remain fixture_only");
  if (config.provider !== "ruby_first_party_quick_pickup") {
    throw new Error("quick pickup provider must be ruby_first_party_quick_pickup");
  }
  if (config.air_mobile_order_required_for_v1 !== false) {
    throw new Error("Air Mobile Order must not be a V1 Quick Pickup dependency");
  }

  for (const key of [
    "route_implemented",
    "eligible_catalog_confirmed",
    "inventory_freshness_control_green",
    "capacity_and_cutoff_control_green",
    "checkout_and_payment_contract_green",
    "bilingual_customer_copy_green",
    "controlled_handset_and_operator_acceptance_green",
    "rollback_disable_path_green",
    "activation_authorized",
    "automatic_production_execution_authorized",
  ]) {
    if (typeof config[key] !== "boolean") throw new TypeError(`${key} must be boolean`);
  }

  if (config.automatic_production_execution_authorized !== false) {
    throw new Error("automatic Quick Pickup execution must remain disabled");
  }

  if (config.customer_route !== null && (typeof config.customer_route !== "string" || !config.customer_route.startsWith("/"))) {
    throw new TypeError("customer_route must be null or a site-relative path");
  }
  if (!config.route_implemented && config.customer_route !== null) {
    throw new Error("unimplemented Quick Pickup must not expose a customer route");
  }
  const readiness = [
    "route_implemented",
    "eligible_catalog_confirmed",
    "inventory_freshness_control_green",
    "capacity_and_cutoff_control_green",
    "checkout_and_payment_contract_green",
    "bilingual_customer_copy_green",
    "controlled_handset_and_operator_acceptance_green",
    "rollback_disable_path_green",
  ];
  if (config.activation_authorized && readiness.some((key) => config[key] !== true)) {
    throw new Error("activation_authorized requires every first-party readiness gate");
  }

  return config;
}

export function firstPartyQuickPickupUiState(config) {
  validateFirstPartyQuickPickupConfig(config);
  const available = Boolean(config.route_implemented && config.customer_route && config.activation_authorized);
  return Object.freeze({
    available,
    href: available ? config.customer_route : null,
    reason: available
      ? "controlled_activation_ready"
      : config.route_implemented
        ? "readiness_pending"
        : "implementation_pending",
  });
}
