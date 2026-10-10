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

let liveSessionToken = null;
let liveRefreshTimer = null;

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

function renderCountList(target, values, emptyLabel) {
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
}

function renderTaskComposition(data) {
  const composition = data.task_composition ?? {};
  renderCountList(document.querySelector("#task-source-list"), composition.by_source, "No task-source counts in this projection.");
  renderCountList(document.querySelector("#task-type-list"), composition.by_type, "No task-type counts in this projection.");
  document.querySelector("#task-duplicate-chip").textContent = `${composition.duplicate_tasks ?? 0} duplicate${composition.duplicate_tasks === 1 ? "" : "s"}`;
}

function renderApproval(data) {
  const approval = data.approval ?? {};
  const rows = [
    ["Tracked plans", approval.plan_count],
    ["Recorded decisions", approval.decision_count],
    ["Awaiting decision", approval.awaiting_decision],
    ["Simulation releasable", approval.simulation_releasable],
  ];
  document.querySelector("#approval-list").replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = "off";
    dd.textContent = text(value ?? 0);
    row.append(dt, dd);
    return row;
  }));
  renderCountList(document.querySelector("#approval-state-list"), approval.by_state, "No approval-state counts in this projection.");
  document.querySelector("#approval-chip").textContent = approval.awaiting_decision ? `${approval.awaiting_decision} awaiting decision` : "clear";
}

function renderRecovery(data) {
  const recovery = data.recovery ?? {};
  const rows = [
    ["Recovery plans", recovery.plan_count],
    ["Retry simulation candidates", recovery.retry_simulation_count],
    ["Stopped for review", recovery.stop_for_review_count],
    ["Duplicate plans", recovery.duplicate_plans],
  ];
  document.querySelector("#recovery-list").replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.className = "off";
    dd.textContent = text(value ?? 0);
    row.append(dt, dd);
    return row;
  }));
  renderCountList(document.querySelector("#recovery-error-list"), recovery.error_code_counts, "No simulated recovery error codes in this projection.");
  document.querySelector("#recovery-chip").textContent = recovery.stop_for_review_count ? `${recovery.stop_for_review_count} needs review` : "clear";
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

function renderChannelReadiness(data) {
  const list = document.querySelector("#channel-readiness-list");
  const channels = data.channels ?? [];
  document.querySelector("#channel-readiness-chip").textContent = `${data.channel_count ?? 0} gated channels`;
  list.replaceChildren(...channels.map((channel) => {
    const article = document.createElement("article");
    article.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const name = document.createElement("span");
    name.className = "lifecycle-id";
    name.textContent = pretty(channel.channel);
    const chip = document.createElement("span");
    chip.className = "state-chip safe";
    chip.textContent = "not live";
    top.append(name, chip);
    const meta = document.createElement("div");
    meta.className = "lifecycle-meta";
    for (const [label, value] of [
      ["Identity", pretty(channel.identity_state)],
      ["Credentials", channel.credential_introduced ? "introduced" : "not introduced"],
      ["Inbound", channel.inbound_activation_authorized ? "authorized" : "gated"],
      ["Outbound reply", channel.outbound_reply_authorized ? "authorized" : "gated"],
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

function renderProjectReadiness(data) {
  const list = document.querySelector("#project-readiness-list");
  const projects = Array.isArray(data.projects) ? data.projects : [];
  document.querySelector("#project-readiness-chip").textContent = `${projects.length} registered`;
  list.replaceChildren(...projects.map((project) => {
    const article = document.createElement("article");
    article.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const label = document.createElement("span");
    label.className = "lifecycle-id";
    label.textContent = text(project.name ?? project.project_id);
    const chip = document.createElement("span");
    chip.className = "state-chip safe";
    chip.textContent = text(project.mode ?? "read only");
    top.append(label, chip);
    const meta = document.createElement("div");
    meta.className = "lifecycle-meta";
    for (const [labelText, value] of [["Adapter", project.adapter], ["Production cutover", project.production_cutover_authorized ? "authorized" : "not authorized"], ["Mutation", project.mutation_authorized ? "authorized" : "disabled"], ["Customer data", project.customer_data_exposed ? "exposed" : "not exposed"]]) {
      const cell = document.createElement("span");
      cell.textContent = labelText;
      const strong = document.createElement("strong");
      strong.textContent = text(value);
      cell.append(strong);
      meta.append(cell);
    }
    article.append(top, meta);
    return article;
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
    for (const [label, value] of [["Latest stage", item.latest_stage], ["Sequence", item.latest_sequence], ["Audit events", item.event_count]]) {
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
    approval_decision_ids_exposed: "Approval decision IDs",
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
  if (data.version !== 5) throw new Error("Unsupported Mission Control projection version");
  if (data.status !== "read_only" || data.mission_control_mode !== "read_only") throw new Error("Mission Control is not read-only");
  if (data.authority_effect !== "none") throw new Error("Unexpected authority effect");
  for (const [key] of safetyFields) if (data[key] !== false) throw new Error(`Unsafe authority flag: ${key}`);
  if (data.mutation_authorized !== false || data.order_creation_authorized !== false) throw new Error("Mutation/order authority must remain disabled");
  if (data.automation?.simulated_only !== true) throw new Error("Automation projection must remain simulated-only");
  if (data.attention?.read_only !== true) throw new Error("Operator attention projection must remain read-only");
  const tasks = data.task_composition ?? {};
  if (tasks.read_only !== true || tasks.customer_payloads_exposed !== false || tasks.normalized_intent_exposed !== false) throw new Error("Task composition privacy/read-only boundary invalid");
  const approval = data.approval ?? {};
  if (approval.read_only !== true || approval.authority_effect !== "none" || approval.decision_ids_exposed !== false) throw new Error("Approval projection must remain privacy-safe and read-only");
  for (const key of ["automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"]) if (approval[key] !== false) throw new Error(`Unsafe approval flag: ${key}`);
  const recovery = data.recovery ?? {};
  if (recovery.read_only !== true || recovery.authority_effect !== "none") throw new Error("Recovery projection must remain read-only");
  for (const key of ["automatic_retry", "retry_authorized", "automatic_rollback", "rollback_authorized", "execution_authorized", "mutation_authorized"]) if (recovery[key] !== false) throw new Error(`Unsafe recovery flag: ${key}`);
  const control = data.control_plane ?? {};
  if (control.autonomy_level !== "A0" || control.execution_task_class !== "general") throw new Error("Unexpected control-plane baseline");
  if (control.hermes_state !== "idle") throw new Error("Hermes must remain idle in this preview");
  for (const key of ["specialists_enabled", "mission_control_write_enabled", "live_execution_enabled"]) if (control[key] !== false) throw new Error(`Unsafe control-plane flag: ${key}`);
  if (control.operator_decision_required_for_sensitive_actions !== true) throw new Error("Sensitive actions must require operator decision");
}

function assertChannelReadiness(data) {
  if (data.schema !== "phil-ai-os-mission-control-channel-readiness" || data.version !== 1 || data.status !== "read_only") throw new Error("Unexpected channel readiness projection");
  if (data.autonomy_level !== "A0" || data.execution_task_class !== "general" || data.assigned_agent !== "hermes") throw new Error("Channel readiness governance baseline drift");
  if (data.specialists_enabled !== false || data.live_channel_connectivity_authorized !== false || data.outbound_reply_authorized !== false || data.customer_account_mutation_authorized !== false || data.authority_effect !== "none") throw new Error("Unsafe channel readiness authority");
  if (data.controlled_scope_authorized !== true || data.controlled_scope_overrides_preflight !== false) throw new Error("Unsafe controlled channel scope");
  if (data.channel_count !== 5 || !Array.isArray(data.channels) || data.channels.length !== 5) throw new Error("Channel readiness set drift");
  const expected = new Set(["facebook", "instagram", "telegram", "whatsapp", "google_business"]);
  for (const channel of data.channels) {
    if (!expected.delete(channel.channel)) throw new Error("Unexpected or duplicate operations channel");
    for (const key of ["credential_introduced", "live_connectivity_authorized", "inbound_activation_authorized", "outbound_reply_authorized"]) if (channel[key] !== false) throw new Error(`Unsafe channel flag: ${channel.channel}.${key}`);
    if (channel.write_scope_separate_gate !== true) throw new Error(`Channel write scope not separately gated: ${channel.channel}`);
    if (channel.controlled_scope_authorized !== true) throw new Error(`Channel controlled scope missing: ${channel.channel}`);
  }
  if (expected.size) throw new Error("Missing operations channel readiness");
}

function assertProjectReadiness(data) {
  if (data.schema !== "phil-ai-os-mission-control-project-readiness" || data.version !== 1 || data.status !== "read_only" || data.authority_effect !== "none") throw new Error("Unexpected project readiness projection");
  if (!Array.isArray(data.projects)) throw new Error("Project readiness must contain projects");
  for (const project of data.projects) {
    if (project.mutation_authorized !== false || project.production_cutover_authorized !== false || project.customer_data_exposed !== false) throw new Error("Unsafe project readiness authority");
  }
}

function assertConversation(data) {
  if (data.schema !== "phil-ai-os-mission-control-ceo-chief-of-staff-preview" || data.version !== 1) throw new Error("Unexpected conversation preview schema");
  if (data.live !== false || data.authority_effect !== "none" || !Array.isArray(data.messages)) throw new Error("Conversation preview must remain non-live and non-authorizing");
  for (const message of data.messages) {
    if (!message.message_id || !message.conversation_id || !message.body || message.authority_effect !== "none") throw new Error("Conversation message contract invalid");
    if (!["ceo", "chief_of_staff", "agent"].includes(message.sender)) throw new Error("Conversation sender contract invalid");
  }
}

function renderConversation(data) {
  const thread = document.querySelector("#conversation-thread");
  thread.replaceChildren(...data.messages.map((message) => {
    const article = document.createElement("article");
    article.className = `conversation-message ${message.sender}`;
    const top = document.createElement("div");
    top.className = "conversation-message-top";
    const sender = document.createElement("strong");
    sender.textContent = message.sender === "chief_of_staff" ? "Chief of Staff" : message.sender === "ceo" ? "CEO" : "Agent";
    const timestamp = document.createElement("span");
    timestamp.textContent = new Date(message.created_at).toLocaleString();
    top.append(sender, timestamp);
    const body = document.createElement("p");
    body.textContent = message.body;
    article.append(top, body);
    return article;
  }));
}

function renderLiveSummary(snapshot) {
  const target = document.querySelector("#live-control-summary");
  const runtime = snapshot.runtime ?? {};
  const approvals = snapshot.approval_counts ?? {};
  const rows = [
    ["Snapshot status", snapshot.status ?? "unknown"],
    ["Routed execution", runtime.routed_execution_enabled === true ? "enabled" : "disabled"],
    ["Execution kill switch", runtime.execution_kill_switch === true ? "enabled" : "disabled"],
    ["Live test", runtime.live_test_enabled === true ? "enabled" : "disabled"],
    ["Pending approvals", approvals.pending ?? 0],
    ["Approved records", approvals.approved ?? 0],
    ["Denied records", approvals.denied ?? 0],
  ];
  target.replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    if (["disabled", "unknown"].includes(String(value))) dd.className = "off";
    row.append(dt, dd);
    return row;
  }));
  renderLiveAgentPosture(snapshot);
}

function renderLiveAgentPosture(snapshot) {
  const target = document.querySelector("#live-agent-posture");
  const state = document.querySelector("#live-agent-posture-state");
  const model = snapshot.multi_agent ?? snapshot.agent_posture ?? {};
  const agents = Array.isArray(model.agents) ? model.agents : [];
  const handoffs = Array.isArray(model.handoffs) ? model.handoffs : [];
  if (!agents.length && !handoffs.length) {
    state.textContent = "not exposed";
    state.className = "state-chip";
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = "The authenticated snapshot does not expose the multi-agent projection yet.";
    target.replaceChildren(empty);
    return;
  }
  state.textContent = `${agents.length} agents · ${handoffs.length} handoffs`;
  state.className = "state-chip safe";
  const rows = [];
  for (const agent of agents.slice(0, 6)) {
    const id = text(agent.agent_id ?? "agent");
    const readiness = text(agent.readiness?.state ?? "unknown");
    const authority = text(agent.authority_ceiling ?? "unknown");
    rows.push([id, `${readiness} · ceiling ${authority}`]);
  }
  if (handoffs.length) rows.push(["Historical handoffs", `${handoffs.length} recorded`]);
  target.replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    row.className = "safety-row";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    row.append(dt, dd);
    return row;
  }));
}

async function loadLiveAgentPosture(token) {
  const headers = { Authorization: `Bearer ${token}` };
  try {
    const response = await fetch("/api/agent-posture", { cache: "no-store", headers });
    if (response.status === 401) {
      document.querySelector("#live-control-disconnect").click();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderLiveAgentPosture(await response.json());
  } catch (_error) {
    renderLiveAgentPosture({});
  }
}
function recordItems(payload) {
  if (Array.isArray(payload)) return payload;
  for (const key of ["records", "items", "approvals", "executions"]) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

function renderLiveRecords(payload, listSelector, stateSelector, kind) {
  const list = document.querySelector(listSelector);
  const state = document.querySelector(stateSelector);
  const items = recordItems(payload);
  state.textContent = `${items.length} loaded`;
  state.className = "state-chip safe";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = `No recent ${kind} records.`;
    list.replaceChildren(empty);
    return;
  }
  const fields = kind === "approval"
    ? [["State", "state", "status"], ["Requester", "requester", "requested_by"], ["Expires", "expires_at", "expiry"], ["Created", "created_at", "created"]]
    : [["Outcome", "outcome", "status"], ["Task", "task_id", "task"], ["Agent", "agent_id", "agent"], ["Created", "created_at", "created"]];
  list.replaceChildren(...items.slice(0, 10).map((item) => {
    const article = document.createElement("article");
    article.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const label = document.createElement("span");
    label.className = "lifecycle-id";
    label.textContent = kind === "approval" ? "Approval record" : "Execution record";
    const chip = document.createElement("span");
    chip.className = "state-chip";
    chip.textContent = text(item.state ?? item.status ?? item.outcome ?? "recorded");
    top.append(label, chip);
    const meta = document.createElement("div");
    meta.className = "lifecycle-meta";
    for (const [labelText, ...keys] of fields.slice(0, 3)) {
      const cell = document.createElement("span");
      cell.textContent = labelText;
      const strong = document.createElement("strong");
      const value = keys.map((key) => item[key]).find((candidate) => candidate !== undefined && candidate !== null && candidate !== "");
      strong.textContent = text(value);
      cell.append(strong);
      meta.append(cell);
    }
    article.append(top, meta);
    return article;
  }));
}

async function loadLiveRecords(token) {
  const headers = { Authorization: `Bearer ${token}` };
  const results = await Promise.allSettled([
    fetch("/api/approvals", { cache: "no-store", headers }),
    fetch("/api/executions", { cache: "no-store", headers }),
  ]);
  if (results.some((result) => result.status === "fulfilled" && result.value.status === 401)) {
    document.querySelector("#live-control-disconnect").click();
    document.querySelector("#live-control-state").textContent = "session expired";
    return;
  }
  for (const [index, result] of results.entries()) {
    const listSelector = index === 0 ? "#live-approvals-list" : "#live-executions-list";
    const stateSelector = index === 0 ? "#live-approvals-state" : "#live-executions-state";
    const kind = index === 0 ? "approval" : "execution";
    if (result.status === "fulfilled" && result.value.ok) {
      renderLiveRecords(await result.value.json(), listSelector, stateSelector, kind);
    } else {
      const state = document.querySelector(stateSelector);
      state.textContent = "unavailable";
      state.className = "state-chip";
    }
  }
  document.querySelector("#live-records-refreshed").textContent = `Last refreshed ${new Date().toLocaleString()}`;
}

function installLiveRecordsRefresh() {
  const button = document.querySelector("#live-records-refresh");
  button.addEventListener("click", async () => {
    if (!liveSessionToken) return;
    button.disabled = true;
    button.textContent = "Refreshing live records";
    await loadLiveRecords(liveSessionToken);
    button.textContent = "Refresh live records";
    button.disabled = false;
  });
}

function installLiveControlConnection() {
  const form = document.querySelector("#live-control-form");
  const input = document.querySelector("#ceo-token");
  const state = document.querySelector("#live-control-state");
  const disconnect = document.querySelector("#live-control-disconnect");
  const button = form.querySelector("button");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const token = input.value.trim();
    if (!token) {
      state.textContent = "token required";
      return;
    }
    button.disabled = true;
    state.textContent = "connecting";
    try {
      const response = await fetch("/api/snapshot", {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const snapshot = await response.json();
      renderLiveSummary(snapshot);
      liveSessionToken = token;
      document.querySelector("#conversation-message").disabled = false;
      document.querySelector("#decision-request-button").disabled = false;
      document.querySelector("#live-records-refresh").disabled = false;
      disconnect.disabled = false;
      state.textContent = "connected · read only";
      state.className = "state-chip safe";
      const conversationState = document.querySelector("#conversation-state");
      conversationState.textContent = "authenticated · read only";
      conversationState.className = "state-chip safe";
      input.value = "";
      loadLiveRecords(token);
      loadLiveAgentPosture(token);
      if (liveRefreshTimer) clearInterval(liveRefreshTimer);
      liveRefreshTimer = setInterval(() => {
        if (liveSessionToken) loadLiveRecords(liveSessionToken);
        if (liveSessionToken) loadLiveAgentPosture(liveSessionToken);
      }, 60_000);
    } catch (error) {
      state.textContent = `connection failed · ${error.message}`;
      state.className = "state-chip";
      liveSessionToken = null;
      if (liveRefreshTimer) clearInterval(liveRefreshTimer);
      liveRefreshTimer = null;
      document.querySelector("#conversation-message").disabled = true;
      document.querySelector("#decision-request-button").disabled = true;
      document.querySelector("#live-records-refresh").disabled = true;
      disconnect.disabled = true;
      document.querySelector("#live-control-summary").replaceChildren();
      document.querySelector("#live-records-refreshed").textContent = "Not refreshed";
    } finally {
      button.disabled = false;
    }
  });
  disconnect.addEventListener("click", () => {
    liveSessionToken = null;
    if (liveRefreshTimer) clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
    input.value = "";
    document.querySelector("#conversation-message").disabled = true;
    document.querySelector("#decision-request-button").disabled = true;
    document.querySelector("#live-records-refresh").disabled = true;
    disconnect.disabled = true;
    document.querySelector("#live-control-summary").replaceChildren();
    renderLiveAgentPosture({});
    document.querySelector("#live-records-refreshed").textContent = "Not refreshed";
    for (const [listSelector, stateSelector, label] of [
      ["#live-approvals-list", "#live-approvals-state", "approvals"],
      ["#live-executions-list", "#live-executions-state", "executions"],
    ]) {
      const empty = document.createElement("p");
      empty.className = "load-state";
      empty.textContent = `Connect to load recent ${label}.`;
      document.querySelector(listSelector).replaceChildren(empty);
      const recordState = document.querySelector(stateSelector);
      recordState.textContent = "not loaded";
      recordState.className = "state-chip";
    }
    state.textContent = "disconnected";
    state.className = "state-chip";
    document.querySelector("#conversation-state").textContent = "preview · disconnected";
    document.querySelector("#conversation-state").className = "state-chip safe";
  });
}

function installDecisionRequest() {
  const form = document.querySelector("#conversation-composer");
  const input = document.querySelector("#conversation-message");
  const button = document.querySelector("#decision-request-button");
  const state = document.querySelector("#conversation-state");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const taskText = input.value.trim();
    if (!liveSessionToken) {
      state.textContent = "connect read-only first";
      state.className = "state-chip";
      return;
    }
    if (!taskText) {
      state.textContent = "request text required";
      state.className = "state-chip";
      return;
    }
    button.disabled = true;
    state.textContent = "recording decision request";
    state.className = "state-chip";
    try {
      const response = await fetch("/api/decision-requests", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${liveSessionToken}`,
        },
        body: JSON.stringify({
          task_text: taskText,
          conversation_id: "ceo-chief-of-staff",
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      input.value = "";
      state.textContent = "decision request recorded · approval pending";
      state.className = "state-chip safe";
      await loadLiveRecords(liveSessionToken);
    } catch (error) {
      if (error.message === "HTTP 401") {
        document.querySelector("#live-control-disconnect").click();
        state.textContent = "session expired · reconnect required";
        state.className = "state-chip";
        return;
      }
      state.textContent = `request failed · ${error.message}`;
      state.className = "state-chip";
    } finally {
      button.disabled = false;
    }
  });
}

async function boot() {
  const state = document.querySelector("#load-state");
  try {
    const [projectionResponse, channelResponse, conversationResponse, projectResponse] = await Promise.all([
      fetch("./fixture.json", { cache: "no-store" }),
      fetch("./channel-readiness.json", { cache: "no-store" }),
      fetch("./conversation.json", { cache: "no-store" }),
      fetch("./project-readiness.json", { cache: "no-store" }),
    ]);
    if (!projectionResponse.ok) throw new Error(`Projection fixture HTTP ${projectionResponse.status}`);
    if (!channelResponse.ok) throw new Error(`Channel readiness HTTP ${channelResponse.status}`);
    if (!conversationResponse.ok) throw new Error(`Conversation fixture HTTP ${conversationResponse.status}`);
    if (!projectResponse.ok) throw new Error(`Project readiness HTTP ${projectResponse.status}`);
    const [data, channelData, conversationData, projectData] = await Promise.all([projectionResponse.json(), channelResponse.json(), conversationResponse.json(), projectResponse.json()]);
    assertReadOnly(data);
    assertChannelReadiness(channelData);
    assertConversation(conversationData);
    assertProjectReadiness(projectData);
    renderMetrics(data);
    renderTaskComposition(data);
    renderApproval(data);
    renderRecovery(data);
    renderAttention(data);
    renderControlPlane(data);
    renderChannelReadiness(channelData);
    renderProjectReadiness(projectData);
    renderConversation(conversationData);
    renderLifecycles(data);
    renderSafety(data);
    renderPrivacy(data);
    document.querySelector("#authority-effect").textContent = `authority_effect: ${data.authority_effect}`;
    document.querySelector("#simulation-chip").textContent = data.automation.simulated_only ? "simulated only" : "unsafe";
    state.textContent = `${data.operations.tasks} tasks · ${data.operations.tasks_awaiting_approval} awaiting approval · ${data.operations.tasks_ready_for_operator_review} ready for review`;
  } catch (error) {
    state.textContent = `Fail-closed: ${error.message}`;
    for (const selector of ["#metric-grid", "#task-source-list", "#task-type-list", "#approval-list", "#approval-state-list", "#recovery-list", "#recovery-error-list", "#attention-list", "#control-plane-list", "#channel-readiness-list", "#conversation-thread", "#lifecycle-list", "#safety-list", "#privacy-grid"]) document.querySelector(selector)?.replaceChildren();
  }
}

boot();
installLiveControlConnection();
installDecisionRequest();
installLiveRecordsRefresh();
