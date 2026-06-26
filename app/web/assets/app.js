const state = {
  health: null,
  sessions: [],
  sessionId: "",
  messages: [],
  providers: [],
  modelRouting: {},
  ui: {
    default_gating_mode: "gated",
    verbose_trace: true,
  },
  selectedProviderId: "",
  gatingMode: "gated",
  isSending: false,
};

const dom = {
  datasetToday: document.querySelector("#dataset-today"),
  statusBanner: document.querySelector("#status-banner"),
  sessionsList: document.querySelector("#sessions-list"),
  messages: document.querySelector("#messages"),
  providerSelect: document.querySelector("#provider-select"),
  gatingSelect: document.querySelector("#gating-select"),
  questionInput: document.querySelector("#question-input"),
  composerForm: document.querySelector("#composer-form"),
  sendButton: document.querySelector("#send-button"),
  traceVisibilityNote: document.querySelector("#trace-visibility-note"),
  tabButtons: Array.from(document.querySelectorAll(".tab")),
  views: {
    chat: document.querySelector("#view-chat"),
    settings: document.querySelector("#view-settings"),
  },
  newSessionButton: document.querySelector("#new-session-button"),
  uiSettingsForm: document.querySelector("#ui-settings-form"),
  defaultGating: document.querySelector("#settings-default-gating"),
  verboseTrace: document.querySelector("#settings-verbose-trace"),
  addProviderButton: document.querySelector("#add-provider-button"),
  providersForm: document.querySelector("#providers-form"),
  providersList: document.querySelector("#providers-list"),
  intentPrimary: document.querySelector("#intent-primary"),
  intentFallbacks: document.querySelector("#intent-fallbacks"),
  synthesisPrimary: document.querySelector("#synthesis-primary"),
  synthesisFallbacks: document.querySelector("#synthesis-fallbacks"),
  emptyStateTemplate: document.querySelector("#empty-state-template"),
};

document.addEventListener("DOMContentLoaded", () => {
  wireEvents();
  initialize().catch((error) => {
    console.error(error);
    setStatus(error.message || "Failed to load the app.");
  });
});

function wireEvents() {
  dom.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  dom.newSessionButton.addEventListener("click", () => createSession(true));
  dom.gatingSelect.addEventListener("change", () => {
    state.gatingMode = dom.gatingSelect.value;
  });
  dom.providerSelect.addEventListener("change", () => {
    state.selectedProviderId = dom.providerSelect.value;
  });
  dom.composerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage().catch((error) => {
      console.error(error);
      setStatus(error.message || "Chat request failed.");
      state.isSending = false;
      renderMessages();
      updateComposerState();
    });
  });
  dom.uiSettingsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveUISettings().catch((error) => {
      console.error(error);
      setStatus(error.message || "Saving defaults failed.");
    });
  });
  dom.addProviderButton.addEventListener("click", () => {
    state.providers.push(makeBlankProvider());
    renderProviderSettings();
  });
  dom.providersForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveProviderSettings().catch((error) => {
      console.error(error);
      setStatus(error.message || "Saving provider settings failed.");
    });
  });
}

async function initialize() {
  setStatus("Loading workspace");
  const [health, sessions, providersPayload, ui] = await Promise.all([
    api("/health"),
    api("/api/sessions"),
    api("/api/settings/providers"),
    api("/api/settings/ui"),
  ]);
  state.health = health;
  state.sessions = sessions.sessions || [];
  state.providers = providersPayload.llm_providers || [];
  state.modelRouting = providersPayload.model_routing || {};
  state.ui = ui;
  state.gatingMode = ui.default_gating_mode || "gated";

  renderHealth();
  renderSessions();
  renderProviderControls();
  renderProviderSettings();
  renderUISettings();
  updateTraceNote();
  updateComposerState();

  if (state.sessions.length > 0) {
    await openSession(state.sessions[0].id);
  } else {
    renderMessages();
  }

  setStatus("Ready");
}

function renderHealth() {
  dom.datasetToday.textContent = state.health?.dataset_today || "Unknown";
}

function renderSessions() {
  dom.sessionsList.innerHTML = "";
  if (state.sessions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "session-item";
    empty.innerHTML = "<strong>No chats yet</strong><span>Create one to begin.</span>";
    dom.sessionsList.appendChild(empty);
    return;
  }
  state.sessions.forEach((session) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `session-item${session.id === state.sessionId ? " is-active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(session.title || "New chat")}</strong>
      <span>${session.message_count || 0} messages</span>
    `;
    button.addEventListener("click", () => {
      openSession(session.id).catch((error) => {
        console.error(error);
        setStatus(error.message || "Failed to open session.");
      });
    });
    dom.sessionsList.appendChild(button);
  });
}

async function createSession(focusChat = false) {
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title: "New chat" }),
  });
  state.sessions.unshift(session);
  state.sessionId = session.id;
  state.messages = [];
  renderSessions();
  renderMessages();
  if (focusChat) {
    setView("chat");
    dom.questionInput.focus();
  }
  setStatus("New chat ready");
  return session;
}

async function openSession(sessionId) {
  const session = await api(`/api/sessions/${sessionId}`);
  state.sessionId = session.id;
  state.messages = (session.messages || []).map((message) => ({
    role: message.role,
    content: message.content,
    metadata: message.metadata || {},
    created_at: message.created_at || "",
  }));
  renderSessions();
  renderMessages();
}

function renderMessages() {
  dom.messages.innerHTML = "";
  if (state.messages.length === 0) {
    dom.messages.appendChild(dom.emptyStateTemplate.content.cloneNode(true));
    return;
  }
  state.messages.forEach((message) => {
    dom.messages.appendChild(renderMessageCard(message));
  });
  dom.messages.scrollTop = dom.messages.scrollHeight;
}

function renderMessageCard(message) {
  const article = document.createElement("article");
  article.className = `message-card ${message.role}`;

  const head = document.createElement("div");
  head.className = "message-head";
  head.innerHTML = `
    <div class="message-role">${message.role === "assistant" ? "Assistant" : "You"}</div>
    <div class="message-time">${formatTime(message.metadata?.telemetry?.finished_at || message.created_at)}</div>
  `;

  const body = document.createElement("div");
  body.className = "message-content";
  body.innerHTML = formatMultiline(message.content || "");
  article.append(head, body);

  if (message.role === "assistant") {
    const metadata = message.metadata || {};
    if (state.ui.verbose_trace && Array.isArray(metadata.trace_events) && metadata.trace_events.length > 0) {
      const traceSection = document.createElement("div");
      traceSection.className = "message-trace";
      const title = document.createElement("p");
      title.className = "eyebrow";
      title.textContent = "Agent Trace";
      const traceList = document.createElement("div");
      traceList.className = "trace-list";
      metadata.trace_events.forEach((event) => {
        const traceItem = document.createElement("div");
        traceItem.className = "trace-event";
        traceItem.innerHTML = `
          <div class="trace-kind">${escapeHtml(event.kind || "event")}</div>
          <div><strong>${escapeHtml(event.message || "")}</strong></div>
          <div>${escapeHtml(renderTraceDetails(event))}</div>
        `;
        traceList.appendChild(traceItem);
      });
      traceSection.append(title, traceList);
      article.appendChild(traceSection);
    }

    if (metadata.telemetry) {
      article.appendChild(renderMetaRow(metadata));
    }
  }

  return article;
}

function renderMetaRow(metadata) {
  const telemetry = metadata.telemetry || {};
  const totalUsage = telemetry.total_usage || {};
  const row = document.createElement("div");
  row.className = "meta-row";
  row.innerHTML = `
    <span><strong>Gating</strong> ${escapeHtml(metadata.gating_mode || "gated")}</span>
    <span><strong>Intent</strong> ${escapeHtml(telemetry.intent_model || "n/a")}</span>
    <span><strong>Synthesis</strong> ${escapeHtml(telemetry.synthesis_model || "n/a")}</span>
    <span><strong>Tokens</strong> ${Number(totalUsage.total_tokens || 0)}</span>
    <span><strong>In</strong> ${Number(totalUsage.input_tokens || 0)}</span>
    <span><strong>Out</strong> ${Number(totalUsage.output_tokens || 0)}</span>
    <span><strong>Elapsed</strong> ${Number(telemetry.elapsed_ms || 0)} ms</span>
  `;
  return row;
}

function renderProviderControls() {
  dom.providerSelect.innerHTML = '<option value="">Routing default</option>';
  state.providers.forEach((provider) => {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent = `${provider.display_name} (${provider.model_id})`;
    dom.providerSelect.appendChild(option);
  });
  dom.providerSelect.value = state.selectedProviderId;
  dom.gatingSelect.value = state.gatingMode;
}

function renderUISettings() {
  dom.defaultGating.value = state.ui.default_gating_mode || "gated";
  dom.verboseTrace.checked = Boolean(state.ui.verbose_trace);
  dom.gatingSelect.value = state.gatingMode;
}

function renderProviderSettings() {
  renderRoutingControls();
  dom.providersList.innerHTML = "";
  state.providers.forEach((provider, index) => {
    const wrapper = document.createElement("section");
    wrapper.className = "provider-card";
    wrapper.dataset.index = String(index);
    wrapper.innerHTML = `
      <div class="provider-card-head">
        <div>
          <p class="eyebrow">Provider ${index + 1}</p>
          <h3>${escapeHtml(provider.display_name || provider.id || "New provider")}</h3>
        </div>
        <button class="button" type="button" data-action="remove-provider">Remove</button>
      </div>
      <div class="provider-grid">
        <label class="field">
          <span>Provider id</span>
          <input data-field="id" type="text" value="${escapeAttr(provider.id || "")}">
        </label>
        <label class="field">
          <span>Display name</span>
          <input data-field="display_name" type="text" value="${escapeAttr(provider.display_name || "")}">
        </label>
        <label class="field">
          <span>Provider type</span>
          <select data-field="provider_type">${providerTypeOptions(provider.provider_type)}</select>
        </label>
        <label class="field">
          <span>Model id</span>
          <input data-field="model_id" type="text" value="${escapeAttr(provider.model_id || "")}">
        </label>
        <label class="field">
          <span>Auth mode</span>
          <select data-field="auth_mode">${authModeOptions(provider.auth_mode)}</select>
        </label>
        <label class="field">
          <span>Secret ref</span>
          <input data-field="secret_ref" type="text" value="${escapeAttr(provider.secret_ref || "")}">
        </label>
        <label class="field">
          <span>Base URL</span>
          <input data-field="base_url" type="text" value="${escapeAttr(provider.base_url || "")}">
        </label>
        <label class="checkbox-row">
          <input data-field="enabled" type="checkbox"${provider.enabled ? " checked" : ""}>
          <span>Enabled</span>
        </label>
      </div>
      <div class="provider-actions">
        <label class="field grow">
          <span>Stored secret value</span>
          <input data-field="secret_value" type="password" value="">
        </label>
        <button class="button" type="button" data-action="save-secret">Save Secret</button>
        <button class="button" type="button" data-action="clear-secret"${provider.has_secret ? "" : " disabled"}>Clear Secret</button>
      </div>
    `;
    wrapper.addEventListener("click", (event) => handleProviderAction(event, wrapper));
    dom.providersList.appendChild(wrapper);
  });
}

function renderRoutingControls() {
  const options = ['<option value="">None</option>'].concat(
    state.providers.map(
      (provider) => `<option value="${escapeAttr(provider.id)}">${escapeHtml(provider.display_name || provider.id)}</option>`
    )
  );
  dom.intentPrimary.innerHTML = options.join("");
  dom.synthesisPrimary.innerHTML = options.join("");
  dom.intentPrimary.value = state.modelRouting.intent?.primary_provider_id || "";
  dom.synthesisPrimary.value = state.modelRouting.synthesis?.primary_provider_id || "";
  dom.intentFallbacks.value = joinFallbacks(state.modelRouting.intent?.fallback_provider_ids);
  dom.synthesisFallbacks.value = joinFallbacks(state.modelRouting.synthesis?.fallback_provider_ids);
}

function handleProviderAction(event, wrapper) {
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) {
    return;
  }
  const index = Number(wrapper.dataset.index);
  if (actionButton.dataset.action === "remove-provider") {
    state.providers.splice(index, 1);
    renderProviderSettings();
    return;
  }
  if (actionButton.dataset.action === "save-secret") {
    saveSingleSecret(wrapper).catch((error) => {
      console.error(error);
      setStatus(error.message || "Saving secret failed.");
    });
    return;
  }
  if (actionButton.dataset.action === "clear-secret") {
    clearSingleSecret(wrapper).catch((error) => {
      console.error(error);
      setStatus(error.message || "Clearing secret failed.");
    });
  }
}

async function saveUISettings() {
  const payload = {
    default_gating_mode: dom.defaultGating.value,
    verbose_trace: dom.verboseTrace.checked,
  };
  state.ui = await api("/api/settings/ui", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  state.gatingMode = state.ui.default_gating_mode;
  renderUISettings();
  updateTraceNote();
  setStatus("Defaults saved");
}

async function saveProviderSettings() {
  const providers = Array.from(dom.providersList.querySelectorAll(".provider-card")).map((card) =>
    readProviderForm(card)
  );
  const payload = {
    llm_providers: providers,
    model_routing: {
      intent: {
        primary_provider_id: dom.intentPrimary.value.trim(),
        fallback_provider_ids: splitFallbacks(dom.intentFallbacks.value),
      },
      synthesis: {
        primary_provider_id: dom.synthesisPrimary.value.trim(),
        fallback_provider_ids: splitFallbacks(dom.synthesisFallbacks.value),
      },
    },
  };
  const response = await api("/api/settings/providers", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  state.providers = response.llm_providers || [];
  state.modelRouting = response.model_routing || {};
  renderProviderControls();
  renderProviderSettings();
  setStatus("Provider settings saved");
}

async function saveSingleSecret(wrapper) {
  const provider = readProviderForm(wrapper);
  const value = wrapper.querySelector('[data-field="secret_value"]').value;
  if (!provider.secret_ref) {
    throw new Error("Secret ref is required before saving a stored secret.");
  }
  await api(`/api/settings/secrets/${encodeURIComponent(provider.secret_ref)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
  setStatus(`Stored secret for ${provider.id || provider.display_name}`);
}

async function clearSingleSecret(wrapper) {
  const provider = readProviderForm(wrapper);
  if (!provider.secret_ref) {
    throw new Error("Secret ref is required before clearing a stored secret.");
  }
  await api(`/api/settings/secrets/${encodeURIComponent(provider.secret_ref)}`, {
    method: "DELETE",
  });
  setStatus(`Cleared secret for ${provider.id || provider.display_name}`);
}

async function sendMessage() {
  const question = dom.questionInput.value.trim();
  if (!question || state.isSending) {
    return;
  }
  state.isSending = true;
  updateComposerState();
  setStatus("Running assistant");

  if (!state.sessionId) {
    await createSession(false);
  }

  const userMessage = {
    role: "user",
    content: question,
    metadata: {},
    created_at: new Date().toISOString(),
  };
  const assistantMessage = {
    role: "assistant",
    content: "Thinking...",
    metadata: {
      trace_events: [],
      telemetry: {},
      gating_mode: state.gatingMode,
    },
    created_at: new Date().toISOString(),
  };

  state.messages.push(userMessage, assistantMessage);
  renderMessages();
  dom.questionInput.value = "";

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: state.sessionId,
      provider_id: state.selectedProviderId,
      gating_mode: state.gatingMode,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  await consumeNdjson(response, (event) => {
    if (event.type === "trace") {
      assistantMessage.content = "Working through the request...";
      assistantMessage.metadata.trace_events.push(event.event);
      renderMessages();
      return;
    }
    if (event.type === "final") {
      assistantMessage.content = event.response.answer || "";
      assistantMessage.metadata = event.response;
      renderMessages();
      return;
    }
    if (event.type === "error") {
      assistantMessage.content = `Error: ${event.error}`;
      renderMessages();
    }
  });

  state.isSending = false;
  updateComposerState();
  await refreshSessions();
  setStatus("Reply complete");
}

async function refreshSessions() {
  const payload = await api("/api/sessions");
  state.sessions = payload.sessions || [];
  renderSessions();
}

function updateTraceNote() {
  dom.traceVisibilityNote.textContent = state.ui.verbose_trace
    ? "Trace details are visible on assistant cards."
    : "Trace details are hidden by default. Enable them in Settings.";
}

function updateComposerState() {
  dom.sendButton.disabled = state.isSending;
  dom.questionInput.disabled = state.isSending;
  dom.providerSelect.disabled = state.isSending;
  dom.gatingSelect.disabled = state.isSending;
}

function setView(viewName) {
  Object.entries(dom.views).forEach(([name, view]) => {
    view.classList.toggle("is-active", name === viewName);
  });
  dom.tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });
}

function setStatus(message) {
  dom.statusBanner.textContent = message;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      message = payload.detail || JSON.stringify(payload);
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

async function consumeNdjson(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line) {
        onEvent(JSON.parse(line));
      }
      newlineIndex = buffer.indexOf("\n");
    }
  }
  const tail = buffer.trim();
  if (tail) {
    onEvent(JSON.parse(tail));
  }
}

function readProviderForm(card) {
  const valueOf = (name) => card.querySelector(`[data-field="${name}"]`);
  return {
    id: valueOf("id").value.trim(),
    display_name: valueOf("display_name").value.trim(),
    provider_type: valueOf("provider_type").value,
    model_id: valueOf("model_id").value.trim(),
    auth_mode: valueOf("auth_mode").value,
    secret_ref: valueOf("secret_ref").value.trim(),
    base_url: valueOf("base_url").value.trim(),
    enabled: valueOf("enabled").checked,
  };
}

function makeBlankProvider() {
  return {
    id: "",
    display_name: "",
    provider_type: "openai",
    model_id: "",
    auth_mode: "env_var",
    secret_ref: "",
    base_url: "",
    enabled: true,
    has_secret: false,
  };
}

function providerTypeOptions(selected) {
  return [
    "openai",
    "anthropic",
    "google_gemini",
    "mistral",
    "groq",
    "ollama",
    "openai_compatible",
    "openrouter",
    "together",
    "lm_studio",
  ]
    .map((value) => `<option value="${value}"${value === selected ? " selected" : ""}>${value}</option>`)
    .join("");
}

function authModeOptions(selected) {
  return ["env_var", "stored_secret", "none"]
    .map((value) => `<option value="${value}"${value === selected ? " selected" : ""}>${value}</option>`)
    .join("");
}

function splitFallbacks(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinFallbacks(values) {
  return Array.isArray(values) ? values.join(", ") : "";
}

function renderTraceDetails(event) {
  const parts = [];
  if (event.tool_name) {
    parts.push(`tool=${event.tool_name}`);
  }
  if (event.latency_ms) {
    parts.push(`${event.latency_ms}ms`);
  }
  if (event.details) {
    parts.push(JSON.stringify(event.details));
  }
  return parts.join(" · ") || "step";
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatMultiline(value) {
  return escapeHtml(value).replace(/\n/g, "<br>");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}
