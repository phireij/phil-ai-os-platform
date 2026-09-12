const metricLabels = [
  ["channel_events", "Channel events"],
  ["tasks", "Tasks"],
  ["tasks_awaiting_approval", "Awaiting approval"],
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

function text(value) {
  return String(value ?? "—");
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
    chip.textContent = text(item.latest_outcome).replaceAll("_", " ");
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
  if (data.status !== "read_only" || data.mission_control_mode !== "read_only") throw new Error("Mission Control is not read-only");
  if (data.authority_effect !== "none") throw new Error("Unexpected authority effect");
  for (const [key] of safetyFields) if (data[key] !== false) throw new Error(`Unsafe authority flag: ${key}`);
  if (data.mutation_authorized !== false || data.order_creation_authorized !== false) throw new Error("Mutation/order authority must remain disabled");
  if (data.automation?.simulated_only !== true) throw new Error("Automation projection must remain simulated-only");
}

async function boot() {
  const state = document.querySelector("#load-state");
  try {
    const response = await fetch("./fixture.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Projection fixture HTTP ${response.status}`);
    const data = await response.json();
    assertReadOnly(data);
    renderMetrics(data);
    renderLifecycles(data);
    renderSafety(data);
    renderPrivacy(data);
    document.querySelector("#authority-effect").textContent = `authority_effect: ${data.authority_effect}`;
    document.querySelector("#simulation-chip").textContent = data.automation.simulated_only ? "simulated only" : "unsafe";
    state.textContent = `${data.operations.tasks} tasks · ${data.operations.tasks_awaiting_approval} awaiting approval`;
  } catch (error) {
    state.textContent = `Fail-closed: ${error.message}`;
    document.querySelector("#metric-grid").replaceChildren();
    document.querySelector("#lifecycle-list").replaceChildren();
    document.querySelector("#safety-list").replaceChildren();
    document.querySelector("#privacy-grid").replaceChildren();
  }
}

boot();
