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
  ["hermes_state", "Hermes sample state"],
  ["specialists_enabled", "Specialists"],
  ["mission_control_write_enabled", "Mission Control writes"],
  ["live_execution_enabled", "Live execution"],
  ["operator_decision_required_for_sensitive_actions", "Sensitive actions"],
];

let liveSessionToken = null;
let liveRefreshTimer = null;
let liveSessionEpoch = 0;

function text(value) {
  return String(value ?? "—");
}

function pretty(value) {
  return text(value).replaceAll("_", " ");
}

function timestampBasisLabel(value) {
  return ({
    source_updated_at: "Source update time",
    collected_at: "Collection time",
    manual_observation_at: "Manual observation time",
    unset: "Not selected",
  })[value] ?? "Unknown";
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
  document.querySelector("#project-readiness-snapshot").textContent = `Workspace snapshot generated ${text(data.observed_at)} · sources are not queried when this page loads · freshness is classified only where an approved source policy applies`;
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
    for (const [labelText, value] of [["Adapter", project.adapter], ["Evidence", project.evidence_state ?? "unknown"], ["Production cutover", project.production_cutover_authorized ? "authorized" : "not authorized"], ["Mutation", project.mutation_authorized ? "authorized" : "disabled"], ["Customer data", project.customer_data_exposed ? "exposed" : "not exposed"]]) {
      const cell = document.createElement("span");
      cell.textContent = labelText;
      const strong = document.createElement("strong");
      strong.textContent = text(value);
      cell.append(strong);
      meta.append(cell);
    }
    article.append(top, meta);
    if (Array.isArray(project.domain_status) && project.domain_status.length) {
      const domainList = document.createElement("div");
      domainList.className = "lifecycle-list";
      for (const domain of project.domain_status) {
        const evidence = document.createElement("div");
        evidence.className = "lifecycle";
        const evidenceTop = document.createElement("div");
        evidenceTop.className = "lifecycle-top";
        const domainName = document.createElement("span");
        domainName.className = "lifecycle-id";
        domainName.textContent = pretty(domain.domain);
        const state = document.createElement("span");
        state.className = "state-chip";
        state.textContent = `${text(domain.status)} · ${text(domain.freshness)}`;
        evidenceTop.append(domainName, state);
        const evidenceMeta = document.createElement("div");
        evidenceMeta.className = "lifecycle-meta";
        for (const [labelText, value] of [["Source ID", domain.source_id], ["Candidate system", domain.candidate_system], ["Authority scope", domain.authority_scope], ["Source state", domain.source_state], ["Freshness policy", pretty(domain.freshness_policy_status)], ["Timestamp basis", timestampBasisLabel(domain.freshness_timestamp_basis)], ["Policy version", domain.freshness_policy_version ?? "not applied"], ["Source reference", domain.source_reference ?? "not recorded"], ["Observed", domain.observed_at ?? "not observed"], ["Source updated at", domain.source_updated_at ?? "not recorded"], ["Collected at", domain.collected_at ?? "not recorded"], ["Manual observation at", domain.manual_observation_at ?? "not recorded"], ["Age", Number.isInteger(domain.age_seconds) ? `${domain.age_seconds}s` : "not computed"], ["Status note", domain.freshness_reason ?? domain.reason]]) {
          const cell = document.createElement("span");
          cell.textContent = labelText;
          const detail = document.createElement("strong");
          detail.textContent = text(value);
          cell.append(detail);
          evidenceMeta.append(cell);
        }
        evidence.append(evidenceTop, evidenceMeta);
        if (domain.evidence_summary?.kind === "github_ci_exact_main") {
          const summary = document.createElement("p");
          summary.className = "lifecycle-meta";
          const workflows = domain.evidence_summary.workflows.map((workflow) => `${workflow.name}: ${workflow.state}/${workflow.conclusion ?? "no conclusion"} · updated ${workflow.updated_at ?? "timestamp unavailable"}`).join(" · ");
          summary.textContent = `Exact main ${domain.evidence_summary.main_head_sha} · ${workflows} · CI evidence does not establish overall project readiness.`;
          evidence.append(summary);
        }
        domainList.append(evidence);
      }
      article.append(domainList);
    }
    return article;
  }));
}

function assertNotificationReadModel(data) {
  if (data.schema !== "phil-ai-os-mission-control-notification-read-model" || data.version !== 1) throw new Error("Unexpected notification read model");
  if (!["available", "unavailable", "not_configured"].includes(data.read_state) || !["fresh", "stale", "unknown"].includes(data.freshness) || !Array.isArray(data.items)) throw new Error("Invalid notification read state");
  if (data.authority?.authority_effect !== "none" || data.authority?.mutation_authorized !== false || data.authority?.notification_send_authorized !== false) throw new Error("Notification projection must remain read only");
  if (data.read_state !== "available" && (data.freshness !== "unknown" || data.items.length !== 0)) throw new Error("Unavailable notification data must remain empty and unknown");
  if (data.read_state === "available" && !data.generated_at) throw new Error("Available notification data needs an observation time");
  if (data.freshness !== "unknown" && !data.freshness_policy_version) throw new Error("Notification freshness requires a policy version");
  for (const item of data.items) {
    if (!item.event_id || !item.approval_id || !item.task_id || item.event_type !== "approval_pending" || item.channel !== "telegram" || !["pending", "leased", "retry_wait", "delivered", "dead_letter"].includes(item.state)) throw new Error("Invalid approval notification evidence");
    if (!Number.isInteger(item.attempt_count) || item.attempt_count < 0) throw new Error("Invalid notification attempt count");
  }
}

function renderNotificationReadModel(data) {
  const list = document.querySelector("#notification-list");
  const chip = document.querySelector("#notification-state-chip");
  chip.textContent = pretty(data.read_state);
  chip.className = data.read_state === "available" ? "state-chip safe" : "state-chip";
  if (data.read_state !== "available") {
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = data.read_state === "not_configured"
      ? "The approval outbox read projection is not connected in this preview. Delivery and retry state are unavailable here."
      : "The approval outbox source is unavailable. Delivery state is unknown.";
    list.replaceChildren(empty);
    return;
  }
  if (!data.items.length) {
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = "No approval notification records were returned by the source.";
    list.replaceChildren(empty);
    return;
  }
  list.replaceChildren(...data.items.map((item) => {
    const row = document.createElement("article");
    row.className = "lifecycle";
    const top = document.createElement("div");
    top.className = "lifecycle-top";
    const title = document.createElement("span");
    title.className = "lifecycle-id";
    title.textContent = `${text(item.event_id)} · ${pretty(item.state)}`;
    const channel = document.createElement("span");
    channel.className = "state-chip";
    channel.textContent = text(item.channel);
    top.append(title, channel);
    const meta = document.createElement("div");
    meta.className = "lifecycle-meta";
    for (const [label, value] of [["Approval", item.approval_id], ["Task", item.task_id], ["Attempts", item.attempt_count], ["Updated", item.updated_at], ["Delivered", item.delivered_at ?? "not delivered"], ["Last error", item.last_error_code ?? "none"]]) {
      const cell = document.createElement("span");
      cell.textContent = label;
      const detail = document.createElement("strong");
      detail.textContent = text(value);
      cell.append(detail);
      meta.append(cell);
    }
    row.append(top, meta);
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
  if (data.schema !== "phil-ai-os-mission-control-project-readiness" || data.version !== 1 || data.status !== "read_only" || data.authority_effect !== "none" || !data.observed_at || !data.source) throw new Error("Unexpected project readiness projection");
  if (!Array.isArray(data.projects)) throw new Error("Project readiness must contain projects");
  for (const project of data.projects) {
    if (project.mutation_authorized !== false || project.production_cutover_authorized !== false || project.customer_data_exposed !== false || !["contract_verified", "source_observed", "partial", "unknown"].includes(project.evidence_state)) throw new Error("Unsafe project readiness authority");
    if (project.domain_status !== undefined) {
      if (!Array.isArray(project.domain_status)) throw new Error("Project domain status must be an array");
      for (const domain of project.domain_status) {
        if (!domain.source_id || !domain.candidate_system || !domain.authority_scope || !domain.source_state || !["green", "yellow", "red", "unknown"].includes(domain.status) || !["fresh", "stale", "unknown"].includes(domain.freshness) || !["not_defined", "proposed", "approved", "retired"].includes(domain.freshness_policy_status) || !["source_updated_at", "collected_at", "manual_observation_at", "unset"].includes(domain.freshness_timestamp_basis) || !domain.reason) throw new Error("Project domain status contract is invalid");
        if (!Object.hasOwn(domain, "evidence_summary")) throw new Error("Project evidence summary field is required");
        const summary = domain.evidence_summary;
        if (summary !== null) {
          const expectedWorkflows = ["Project State Observation CI", "Workflow Supply-Chain Policy CI"];
          const summaryKeys = ["evidence_state", "expected_run_branch", "kind", "main_head_sha", "workflows"].sort();
          if (domain.source_id !== "phil-ai-os.repository-ci" || domain.freshness !== "fresh" || Object.keys(summary).sort().join("|") !== summaryKeys.join("|") || summary.kind !== "github_ci_exact_main" || summary.evidence_state !== "observed" || summary.expected_run_branch !== "main" || !/^[0-9a-f]{40}$/.test(summary.main_head_sha ?? "") || !Array.isArray(summary.workflows) || summary.workflows.length !== expectedWorkflows.length) throw new Error("Only fresh exact-main CI evidence may carry a summary");
          const workflowKeys = ["conclusion", "name", "state", "updated_at"].sort();
          if (summary.workflows.some((workflow) => !workflow || typeof workflow !== "object" || Object.keys(workflow).sort().join("|") !== workflowKeys.join("|") || (workflow.updated_at !== null && (typeof workflow.updated_at !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(workflow.updated_at))))) throw new Error("CI evidence summary contains unsupported fields or timestamps");
          const names = summary.workflows.map((workflow) => workflow.name);
          if (expectedWorkflows.some((name, index) => names[index] !== name) || summary.workflows.some((workflow) => !["queued", "in_progress", "completed", "requested", "waiting", "pending"].includes(workflow.state) || (workflow.conclusion !== null && !["success", "failure", "neutral", "cancelled", "timed_out", "action_required", "stale", "skipped", "startup_failure"].includes(workflow.conclusion)))) throw new Error("CI evidence summary contains an unsupported workflow result");
        }
        if (domain.freshness !== "fresh" && domain.status !== "unknown") throw new Error("Stale or unclassified project evidence cannot assert a current domain status");
        if (domain.freshness_policy_status !== "approved" && (domain.freshness !== "unknown" || domain.status !== "unknown" || domain.age_seconds != null || domain.freshness_policy_version != null || (domain.freshness_policy_status === "proposed" ? domain.freshness_timestamp_basis === "unset" : domain.freshness_timestamp_basis !== "unset"))) throw new Error("Project evidence without an approved freshness policy must remain unknown and unclassified");
        if (domain.freshness_policy_status === "approved" && (!domain.freshness_policy_version || domain.freshness_timestamp_basis === "unset" || typeof domain.freshness_reason !== "string" || !domain.freshness_reason.trim())) throw new Error("Approved project policy requires version, timestamp basis, and freshness reason even when evidence is unknown");
        if (["fresh", "stale"].includes(domain.freshness) && (domain.freshness_policy_status !== "approved" || !domain.observed_at || !domain.freshness_policy_version || !Number.isInteger(domain.age_seconds) || domain.age_seconds < 0 || !domain.source_reference || typeof domain.freshness_reason !== "string" || !domain.freshness_reason.trim())) throw new Error("Classified project status requires approved policy, provenance, and computed age");
      }
    }
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
  const agentsAvailable = snapshot.agents_available === true;
  const handoffsAvailable = snapshot.handoffs_available === true;
  const agentsTruncated = snapshot.agents_truncated === true;
  const handoffsTruncated = snapshot.handoffs_truncated === true;
  const sourceGeneratedAt = typeof snapshot.source_generated_at === "string" ? snapshot.source_generated_at : null;
  if (!agentsAvailable && !handoffsAvailable) {
    state.textContent = "posture data unavailable · freshness not evaluated";
    state.className = "state-chip";
    const empty = document.createElement("p");
    empty.className = "load-state";
    empty.textContent = "The authenticated snapshot did not provide agent or handoff evidence.";
    const rows = sourceGeneratedAt ? [empty, Object.assign(document.createElement("p"), { textContent: `Upstream snapshot generated · freshness not evaluated: ${sourceGeneratedAt}` })] : [empty];
    target.replaceChildren(...rows);
    return;
  }
  const agentSummary = agentsAvailable ? `${agentsTruncated ? "at least " : ""}${agents.length} agents` : "agents unavailable";
  const handoffSummary = handoffsAvailable ? `${handoffsTruncated ? "at least " : ""}${handoffs.length} handoffs` : "handoffs unavailable";
  state.textContent = `${agentSummary} · ${handoffSummary} · freshness not evaluated`;
  state.className = "state-chip";
  const rows = sourceGeneratedAt ? [["Upstream snapshot generated · freshness not evaluated", sourceGeneratedAt]] : [];
  if (agentsAvailable) {
    for (const agent of agents.slice(0, 6)) {
      const id = text(agent.agent_id ?? "unknown agent");
      const readiness = displayAgentReadiness(agent, sourceGeneratedAt);
      const authority = text(agent.authority_ceiling ?? "unknown");
      rows.push([id, `${readiness} · ceiling ${authority}`]);
      const presence = agent.presence ?? {};
      const presenceState = ["fresh", "stale", "offline", "unknown"].includes(presence.state) ? presence.state : "unknown";
      const presenceObservedAt = typeof presence.observed_at === "string" ? presence.observed_at : "not recorded";
      const presenceAge = Number.isSafeInteger(presence.age_seconds) && presence.age_seconds >= 0
        ? `${presence.age_seconds}s (source-reported)`
        : "not recorded";
      rows.push([`A7 presence · ${id}`, `${presenceState} · observed ${presenceObservedAt} · age ${presenceAge}`]);
    }
  }
  if (handoffsAvailable && handoffs.length) rows.push(["Historical handoffs", `${handoffsTruncated ? "At least " : ""}${handoffs.length} recorded`]);
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

function displayAgentReadiness(agent, sourceGeneratedAt) {
  const registry = agent.registry ?? {};
  const presence = agent.presence ?? {};
  const workload = agent.workload ?? {};
  const readiness = agent.readiness ?? {};
  const evidenceComplete = [
    agent.evidence_complete,
    registry.evidence_complete,
    presence.evidence_complete,
    workload.evidence_complete,
  ].every((value) => value === true)
    && presence.identity_verified === true
    && typeof presence.observed_at === "string"
    && Number.isSafeInteger(presence.age_seconds)
    && presence.age_seconds >= 0
    && presence.age_seconds <= 120
    && typeof sourceGeneratedAt === "string"
    && Date.parse(presence.observed_at) <= Date.parse(sourceGeneratedAt)
    && typeof registry.enabled === "boolean"
    && typeof registry.assignable === "boolean"
    && Number.isSafeInteger(workload.active_task_count)
    && workload.active_task_count >= 0
    && readiness.grants_authority === false;
  if (!evidenceComplete) return "indeterminate · evidence incomplete";

  const sourceState = readiness.state;
  if (sourceState === "ready") {
    const readyEvidence = registry.enabled === true
      && registry.assignable === true
      && presence.state === "fresh"
      && workload.active_task_count === 0;
    return readyEvidence ? "ready" : "indeterminate · conflicting evidence";
  }
  return typeof sourceState === "string" ? sourceState : "indeterminate";
}

async function loadLiveAgentPosture(token, epoch = liveSessionEpoch) {
  const headers = { Authorization: `Bearer ${token}` };
  try {
    const response = await fetch("/api/agent-posture", { cache: "no-store", headers });
    if (epoch !== liveSessionEpoch || !liveSessionToken) return;
    if (response.status === 401) {
      document.querySelector("#live-control-disconnect").click();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (epoch !== liveSessionEpoch || !liveSessionToken) return;
    if (payload?.contract_version !== 2) {
      renderLiveAgentPosture({});
      const state = document.querySelector("#live-agent-posture-state");
      state.textContent = "unsupported bridge contract";
      return;
    }
    renderLiveAgentPosture(payload);
  } catch (_error) {
    if (epoch === liveSessionEpoch && liveSessionToken) {
      renderLiveAgentPosture({});
      document.querySelector("#live-agent-posture-state").textContent = "bridge unavailable";
    }
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

async function loadLiveRecords(token, epoch = liveSessionEpoch) {
  const headers = { Authorization: `Bearer ${token}` };
  const results = await Promise.allSettled([
    fetch("/api/approvals", { cache: "no-store", headers }),
    fetch("/api/executions", { cache: "no-store", headers }),
  ]);
  if (epoch !== liveSessionEpoch || !liveSessionToken) return;
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
      const payload = await result.value.json();
      if (epoch !== liveSessionEpoch || !liveSessionToken) return;
      renderLiveRecords(payload, listSelector, stateSelector, kind);
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
    const epoch = liveSessionEpoch;
    button.disabled = true;
    button.textContent = "Refreshing live records";
    await loadLiveRecords(liveSessionToken, epoch);
    if (epoch === liveSessionEpoch) {
      button.textContent = "Refresh live records";
      button.disabled = !liveSessionToken;
    }
  });
}

function clearAuthenticatedLiveView() {
  document.querySelector("#conversation-message").disabled = true;
  document.querySelector("#decision-request-button").disabled = true;
  const refresh = document.querySelector("#live-records-refresh");
  refresh.disabled = true;
  refresh.textContent = "Refresh live records";
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
  const conversationState = document.querySelector("#conversation-state");
  conversationState.textContent = "sample only · no live chat";
  conversationState.className = "state-chip safe";
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
    const epoch = ++liveSessionEpoch;
    liveSessionToken = null;
    if (liveRefreshTimer) clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
    clearAuthenticatedLiveView();
    disconnect.disabled = true;
    state.textContent = "connecting";
    try {
      const response = await fetch("/api/snapshot", {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const snapshot = await response.json();
      if (epoch !== liveSessionEpoch) return;
      renderLiveSummary(snapshot);
      liveSessionToken = token;
      document.querySelector("#live-records-refresh").disabled = false;
      disconnect.disabled = false;
      state.textContent = "connected · read only";
      state.className = "state-chip safe";
      input.value = "";
      loadLiveRecords(token, epoch);
      loadLiveAgentPosture(token, epoch);
      liveRefreshTimer = setInterval(() => {
        if (liveSessionToken && epoch === liveSessionEpoch) loadLiveRecords(liveSessionToken, epoch);
        if (liveSessionToken && epoch === liveSessionEpoch) loadLiveAgentPosture(liveSessionToken, epoch);
      }, 60_000);
    } catch (error) {
      if (epoch !== liveSessionEpoch) return;
      state.textContent = error.message === "HTTP 403"
        ? "read scope required · connection not established"
        : `connection failed · ${error.message}`;
      state.className = "state-chip";
      liveSessionToken = null;
      if (liveRefreshTimer) clearInterval(liveRefreshTimer);
      liveRefreshTimer = null;
      clearAuthenticatedLiveView();
      disconnect.disabled = true;
    } finally {
      button.disabled = false;
    }
  });
  disconnect.addEventListener("click", () => {
    liveSessionEpoch += 1;
    liveSessionToken = null;
    if (liveRefreshTimer) clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
    input.value = "";
    clearAuthenticatedLiveView();
    disconnect.disabled = true;
    state.textContent = "disconnected";
    state.className = "state-chip";
  });
}

async function boot() {
  const state = document.querySelector("#load-state");
  try {
    const [projectionResponse, channelResponse, conversationResponse, projectResponse, notificationResponse] = await Promise.all([
      fetch("./fixture.json", { cache: "no-store" }),
      fetch("./channel-readiness.json", { cache: "no-store" }),
      fetch("./conversation.json", { cache: "no-store" }),
      fetch("./project-readiness.json", { cache: "no-store" }),
      fetch("./notification-read-model.json", { cache: "no-store" }),
    ]);
    if (!projectionResponse.ok) throw new Error(`Projection fixture HTTP ${projectionResponse.status}`);
    if (!channelResponse.ok) throw new Error(`Channel readiness HTTP ${channelResponse.status}`);
    if (!conversationResponse.ok) throw new Error(`Conversation fixture HTTP ${conversationResponse.status}`);
    if (!projectResponse.ok) throw new Error(`Project readiness HTTP ${projectResponse.status}`);
    if (!notificationResponse.ok) throw new Error(`Notification projection HTTP ${notificationResponse.status}`);
    const [data, channelData, conversationData, projectData, notificationData] = await Promise.all([projectionResponse.json(), channelResponse.json(), conversationResponse.json(), projectResponse.json(), notificationResponse.json()]);
    assertReadOnly(data);
    assertChannelReadiness(channelData);
    assertConversation(conversationData);
    assertProjectReadiness(projectData);
    assertNotificationReadModel(notificationData);
    renderMetrics(data);
    renderTaskComposition(data);
    renderApproval(data);
    renderRecovery(data);
    renderAttention(data);
    renderControlPlane(data);
    renderChannelReadiness(channelData);
    renderProjectReadiness(projectData);
    renderNotificationReadModel(notificationData);
    renderConversation(conversationData);
    renderLifecycles(data);
    renderSafety(data);
    renderPrivacy(data);
    document.querySelector("#authority-effect").textContent = `authority_effect: ${data.authority_effect}`;
    document.querySelector("#simulation-chip").textContent = data.automation.simulated_only ? "simulated only" : "unsafe";
    state.textContent = `SYNTHETIC FIXTURE · ${data.operations.tasks} sample tasks · ${data.operations.tasks_awaiting_approval} awaiting approval · ${data.operations.tasks_ready_for_operator_review} ready for review`;
  } catch (error) {
    state.textContent = `Fail-closed: ${error.message}`;
    for (const selector of ["#metric-grid", "#task-source-list", "#task-type-list", "#approval-list", "#approval-state-list", "#recovery-list", "#recovery-error-list", "#attention-list", "#control-plane-list", "#channel-readiness-list", "#conversation-thread", "#project-readiness-list", "#notification-list", "#lifecycle-list", "#safety-list", "#privacy-grid"]) document.querySelector(selector)?.replaceChildren();
  }
}

boot();
installLiveControlConnection();
installLiveRecordsRefresh();
