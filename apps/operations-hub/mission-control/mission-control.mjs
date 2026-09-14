const metricLabels = [
  ["channel_events", "Channel events"],
  ["tasks", "Tasks"],
  ["tasks_awaiting_approval", "Awaiting approval"],
  ["tasks_ready_for_operator_review", "Ready for operator review"],
  ["orders_pending_staff_review", "Orders for staff review"],
  ["quotes_pending_approval", "Quotes pending approval"],
  ["owner_review_pending_packets", "Owner review packets"],
];

const safetyFields = [
  ["execution_authorized", "Execution"],
  ["channel_reply_authorized", "Customer replies"],
  ["network_dispatch_authorized", "Network dispatch"],
  ["woo_commerce_mutation_authorized", "WooCommerce mutation"],
  ["payment_execution_authorized", "Payment execution"],
  ["sms_send_authorized", "SMS send"],
  ["inventory_mutation_authorized", "Inventory mutation"],
  ["production_publish_authorized", "Production publish"],
];

const controlPlaneFields = [
  ["autonomy_level", "Autonomy level"],
  ["execution_task_class", "Execution task class"],
  ["hermes_state", "Hermes"],
  ["specialists_enabled", "Specialists"],
  ["mission_control_write_enabled", "Mission Control writes"],
  ["live_execution_enabled", "Live execution"],
  ["operator_decision_required_for_sensitive_actions", "Sensitive actions"],
];

function text(value) {
  return String(value ?? "—");
}

function pretty(value) {
  return text(value).replaceAll("_", " ");
}

function renderMetrics(data) {
  const grid = document.querySelector("#metric-grid");
  grid.replaceChildren(...metricLabels.map(([key, label]) => {
    const card = document.createElement("article");
    card.className = `metric${key.includes("approval") || key.includes("review") ? " attention" : ""}`;
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = text(data.operations?.[key] ?? 0);
    card.append(labelNode, valueNode);
    return card;
  }));
}

function renderTaskComposition(data) {
  const sourceList = document.querySelector("#task-source-list");
  const typeList = document.querySelector("#task-type-list");
  const composition = data.task_composition ?? {};

  const renderCounts = (target, values, emptyLabel) => {
    const entries = Object.entries(values ?? {});
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.className = "load-state";
      empty.textContent = emptyLabel;
      target.replaceChildren(empty);
      return;
    }
    target.replaceChildren(...entries.map(([label, count]) => {
      const row = document.createElement("div");
      row.className = "safety-row";
      const dt = document.createElement("dt");
      dt.textContent = pretty(label);
      const dd = document.createElement("dd");
      dd.className = "off";
      dd.textContent = text(count);
      row.append(dt, dd);
      return row;
    }));
  };

  renderCounts(sourceList, composition.by_source, "No task-source counts in this projection.");
  renderCounts(typeList, composition.by_type, "No task-type counts in this projection.");
  document.querySelector("#task-duplicate-chip").textContent = `${composition.duplicate_tasks ?? 0} duplicate${composition.duplicate_tasks === 1 ? "" : "s"}`;
}

function renderAttention(data) {
  const list = document.querySelector("#attention-list");
  const items = data.attention?.items ?? [];
  document.querySelector("#attention-chip").textContent = `${data.attention?.count ?? 0} items`;
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = "No bounded operator-attention items in this projection.";
    list.replaceChildren(empty);
    return;
  }
  list.replaceChildren(...items.map((item) => {
    const article = document.createElement("article");
    article.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const label = document.createElement("span");
    label.className = "lifecycle-id";
    label.textContent = text(item.label);
    const chip = document.createElement("span");
    chip.className = "state-chip";
    chip.textContent = `${text(item.count)} · ${text(item.priority)}`;
    top.append(label, chip);
    article.append(top);
    return article;
  }));
}

function renderControlPlane(data) {
  const list = document.querySelector("#control-plane-list");
  list.replaceChildren(...controlPlaneFields.map(([key, label]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    const value = data.control_plane?.[key];
    if (key === "operator_decision_required_for_sensitive_actions") {
      dd.textContent = value === true ? "OPERATOR REQUIRED" : "UNSAFE";
      if (value === true) dd.className = "off";
    } else if (typeof value === "boolean") {
      dd.textContent = value ? "ENABLED" : "DISABLED";
      if (value === false) dd.className = "off";
    } else {
      dd.textContent = text(value).toUpperCase();
      dd.className = "off";
    }
    row.append(dt, dd);
    return row;
  }));
}

function renderLifecycles(data) {
  const list = document.querySelector("#lifecycle-list");
  const lifecycles = data.automation?.lifecycles ?? [];
  if (!lifecycles.length) {
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = "No simulated lifecycle items in this projection.";
    list.replaceChildren(empty);
    return;
  }
  list.replaceChildren(...lifecycles.map((item) => {
    const article = document.createElement("article");
    article.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const id = document.createElement("span");
    id.className = "lifecycle-id";
    id.textContent = text(item.lifecycle_correlation_id);
    const chip = document.createElement("span");
    chip.className = "state-chip";
    chip.textContent = pretty(item.latest_outcome);
    top.append(id, chip);
    const meta = document.createElement("div");
    meta.className = "lifecycle-meta";
    for (const [label, value] of [
      ["Latest stage", item.latest_stage],
      ["Sequence", item.latest_sequence],
      ["Audit events", item.event_count],
    ]) {
      const cell = document.createElement("span");
      cell.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = text(value);
      cell.append(strong);
      meta.append(cell);
    }
    article.append(top, meta);
    return article;
  }));
}

function renderSafety(data) {
  const list = document.querySelector("#safety-list");
  list.replaceChildren(...safetyFields.map(([key, label]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = data[key] === false ? "off" : "";
    dd.textContent = data[key] === false ? "DISABLED" : "UNSAFE";
    row.append(dt, dd);
    return row;
  }));
}

function renderPrivacy(data) {
  const grid = document.querySelector("#privacy-grid");
  const labels = {
    raw_customer_text_exposed: "Raw customer text",
    custom_notes_exposed: "Custom notes",
    reference_image_names_exposed: "Reference image names",
    reply_draft_text_exposed: "Reply draft text",
  };
  grid.replaceChildren(...Object.entries(labels).map(([key, label]) => {
    const item = document.createElement("div");
    item.className = "privacy-item";
    const status = document.createElement("strong");
    status.textContent = data.privacy?.[key] === false ? "NOT EXPOSED" : "CHECK REQUIRED";
    const copy = document.createElement("span");
    copy.textContent = label;
    item.append(status, copy);
    return item;
  }));
}

function assertReadOnly(data) {
  if (data.schema !== "phil-ai-os-mission-control-lifecycle-projection") throw new Error("Unexpected projection schema");
  if (data.version !== 3) throw new Error("Unsupported Mission Control projection version");
  if (data.status !== "read_only" || data.mission_control_mode !== "read_only") throw new Error("Mission Control is not read-only");
  if (data.authority_effect !== "none") throw new Error("Unexpected authority effect");
  for (const [key] of safetyFields) if (data[key] !== false) throw new Error(`Unsafe authority flag: ${key}`);
  if (data.mutation_authorized !== false || data.order_creation_authorized !== false) throw new Error("Mutation/order authority must remain disabled");
  if (data.automation?.simulated_only !== true) throw new Error("Automation projection must remain simulated-only");
  if (data.attention?.read_only !== true) throw new Error("Operator attention projection must remain read-only");
  const tasks = data.task_composition ?? {};
  if (tasks.read_only !== true || tasks.customer_payloads_exposed !== false || tasks.normalized_intent_exposed !== false) {
    throw new Error("Task composition privacy/read-only boundary invalid");
  }
  const control = data.control_plane ?? {};
  if (control.autonomy_level !== "A0" || control.execution_task_class !== "general") throw new Error("Unexpected control-plane baseline");
  if (control.hermes_state !== "idle") throw new Error("Hermes must remain idle in this preview");
  for (const key of ["specialists_enabled", "mission_control_write_enabled", "live_execution_enabled"]) {
    if (control[key] !== false) throw new Error(`Unsafe control-plane flag: ${key}`);
  }
  if (control.operator_decision_required_for_sensitive_actions !== true) throw new Error("Sensitive actions must require operator decision");
}

async function boot() {
  const state = document.querySelector("#load-state");
  try {
    const response = await fetch("./fixture.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Projection fixture HTTP ${response.status}`);
    const data = await response.json();
    assertReadOnly(data);
    renderMetrics(data);
    renderTaskComposition(data);
    renderAttention(data);
    renderControlPlane(data);
    renderLifecycles(data);
    renderSafety(data);
    renderPrivacy(data);
    document.querySelector("#authority-effect").textContent = `authority_effect: ${data.authority_effect}`;
    document.querySelector("#simulation-chip").textContent = data.automation.simulated_only ? "simulated only" : "unsafe";
    state.textContent = `${data.operations.tasks} tasks · ${data.operations.tasks_awaiting_approval} awaiting approval · ${data.operations.tasks_ready_for_operator_review} ready for review`;
  } catch (error) {
    state.textContent = `Fail-closed: ${error.message}`;
    for (const selector of ["#metric-grid", "#task-source-list", "#task-type-list", "#attention-list", "#control-plane-list", "#lifecycle-list", "#safety-list", "#privacy-grid"]) {
      document.querySelector(selector)?.replaceChildren();
    }
  }
}

boot();
