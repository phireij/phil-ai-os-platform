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
