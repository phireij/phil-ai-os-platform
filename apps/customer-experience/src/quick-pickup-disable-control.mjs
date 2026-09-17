const FALSE_AUTHORITY_KEYS = [
  "network_authorized",
  "route_mutation_authorized",
  "inventory_mutation_authorized",
  "capacity_mutation_authorized",
  "order_creation_authorized",
  "payment_execution_authorized",
  "production_publish_authorized",
];

export function validateQuickPickupDisableControl(control) {
  if (control?.fixture_only !== true) throw new Error("Quick Pickup disable control must remain fixture_only");
  if (typeof control.control_id !== "string" || !control.control_id.startsWith("fixture:")) {
    throw new TypeError("Quick Pickup disable control_id must be fixture-scoped");
  }
  if (control.mode !== "operator_hold") throw new Error("Quick Pickup disable control mode must remain operator_hold");
  if (typeof control.disable_engaged !== "boolean") throw new TypeError("disable_engaged must be boolean");
  if (typeof control.reason !== "string" || control.reason.length === 0) throw new TypeError("disable reason is required");
  for (const key of FALSE_AUTHORITY_KEYS) {
    if (control[key] !== false) throw new Error(`${key} must remain false`);
  }
  return control;
}

export function applyQuickPickupDisableControl(routeState, control) {
  validateQuickPickupDisableControl(control);
  if (!routeState || typeof routeState.available !== "boolean") {
    throw new TypeError("Quick Pickup route state is required");
  }
  if (routeState.href !== null && typeof routeState.href !== "string") {
    throw new TypeError("Quick Pickup route href must be null or string");
  }
  if (typeof routeState.reason !== "string" || routeState.reason.length === 0) {
    throw new TypeError("Quick Pickup route reason is required");
  }

  if (control.disable_engaged) {
    return Object.freeze({
      available: false,
      href: null,
      reason: "operator_disable_engaged",
      upstream_reason: routeState.reason,
      disable_control_id: control.control_id,
      disable_reason: control.reason,
      route_activation_authorized: false,
      order_creation_authorized: false,
      payment_execution_authorized: false,
      production_publish_authorized: false,
    });
  }

  return Object.freeze({
    available: routeState.available,
    href: routeState.available ? routeState.href : null,
    reason: routeState.reason,
    upstream_reason: routeState.reason,
    disable_control_id: control.control_id,
    disable_reason: null,
    route_activation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
  });
}
