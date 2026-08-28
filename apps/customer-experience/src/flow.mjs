const ALLOWED = Object.freeze({
  catalog: new Set(["select_product", "fail"]),
  product: new Set(["back_to_catalog", "start_checkout", "fail"]),
  checkout: new Set(["readiness_ready", "readiness_blocked", "edit_product", "fail"]),
  ready: new Set(["edit_product", "back_to_catalog", "fail"]),
  blocked: new Set(["edit_product", "back_to_catalog", "fail"]),
  error: new Set(["recover"]),
});

const NEXT = Object.freeze({
  select_product: "product",
  back_to_catalog: "catalog",
  start_checkout: "checkout",
  readiness_ready: "ready",
  readiness_blocked: "blocked",
  edit_product: "product",
  fail: "error",
  recover: "catalog",
});

export function createCustomerFlow() {
  return Object.freeze({ state: "catalog", mutation_authorized: false, revision: 0 });
}

export function transitionCustomerFlow(flow, event) {
  if (!flow || flow.mutation_authorized !== false) {
    throw new Error("customer flow must remain non-authorizing");
  }
  if (!ALLOWED[flow.state]?.has(event)) {
    throw new Error(`invalid customer flow transition: ${flow.state} -> ${event}`);
  }
  return Object.freeze({
    state: NEXT[event],
    mutation_authorized: false,
    revision: flow.revision + 1,
  });
}
