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
  appearance: {
    theme_mode: "light",
    light_theme: "quiet_light",
    dark_theme: "vscode_dark",
  },
  selectedProviderId: "",
  gatingMode: "bind_all",
  sessionFilter: "active",
  sessionSearch: "",
  archivedSessionIds: new Set(),
  sidebarWidth: 438,
  workspaceHeight: 168,
  isSending: false,
  abortController: null,
  lastQuestion: "",
  commands: [],
  commandMenu: {
    items: [],
    activeIndex: 0,
  },
  providerEditor: {
    selectedIndex: -1,
    draft: null,
    isNew: false,
  },
  providerSort: {
    key: "display_name",
    direction: "asc",
  },
  messageTraceOpen: {},
};

const APPEARANCE_STORAGE_KEY = "solar-ai-appearance";
const UI_STATE_STORAGE_KEY = "solar-ai-ui-state";
const VALID_VIEWS = new Set(["chat", "settings"]);
const VALID_SUBTABS = new Set(["appearance", "ai", "providers", "rag", "config-io"]);
const VALID_GATING_MODES = new Set(["gated", "bind_all"]);
let uiStatePersistTimer = null;
const THEME_PRESETS = {
  vscode_light: {
    bg: "#f3f3f3",
    bgStrong: "#e4e4e4",
    panel: "#ffffff",
    panelStrong: "#f9f9f9",
    ink: "#1f1f1f",
    muted: "#5f6b76",
    line: "rgba(31, 31, 31, 0.10)",
    lineStrong: "rgba(31, 31, 31, 0.18)",
    accent: "#0e639c",
    accentDeep: "#094771",
    accentSoft: "#d9ebf7",
    sage: "#2f7d68",
    user: "#e8eef4",
  },
  quiet_light: {
    bg: "#f6f8fb",
    bgStrong: "#eef2f7",
    panel: "rgba(255, 255, 255, 0.92)",
    panelStrong: "rgba(255, 255, 255, 0.99)",
    ink: "#24292f",
    muted: "#66707b",
    line: "rgba(72, 84, 96, 0.12)",
    lineStrong: "rgba(72, 84, 96, 0.18)",
    accent: "#8f99a4",
    accentDeep: "#737d88",
    accentSoft: "rgba(143, 153, 164, 0.14)",
    sage: "#6f8a78",
    user: "#f4f8fc",
    shadow: "0 18px 42px rgba(31, 35, 40, 0.08)",
    glowTopLeft: "rgba(0, 122, 204, 0.06)",
    glowBottomRight: "rgba(88, 96, 105, 0.06)",
    appbarTop: "color-mix(in srgb, var(--panel-strong) 92%, var(--bg))",
    appbarBottom: "color-mix(in srgb, var(--panel-strong) 92%, var(--bg))",
    appbarInk: "var(--ink)",
    appbarMuted: "var(--muted)",
    appbarSurface: "var(--panel-strong)",
    appbarSurfaceLine: "var(--line)",
    appbarActiveBg: "color-mix(in srgb, var(--panel-strong) 78%, var(--bg))",
    appbarActiveShadow: "0 10px 24px rgba(31, 35, 40, 0.04)",
  },
  cool_light: {
    bg: "#eef4f8",
    bgStrong: "#dce7ef",
    panel: "#fbfdff",
    panelStrong: "#ffffff",
    ink: "#1b2733",
    muted: "#607080",
    line: "rgba(56, 88, 112, 0.14)",
    lineStrong: "rgba(56, 88, 112, 0.22)",
    accent: "#3b82b6",
    accentDeep: "#295d82",
    accentSoft: "#d8ebf6",
    sage: "#4b7a6a",
    user: "#e5eef5",
  },
  sandstone_light: {
    bg: "#f4ecd9",
    bgStrong: "#e7d6b6",
    panel: "#fffdf8",
    panelStrong: "#fffaf1",
    ink: "#2b241d",
    muted: "#726554",
    line: "rgba(98, 75, 44, 0.16)",
    lineStrong: "rgba(98, 75, 44, 0.28)",
    accent: "#9a5d2f",
    accentDeep: "#6f3e16",
    accentSoft: "#ead7bf",
    sage: "#566f60",
    user: "#f3e7d5",
  },
  vscode_dark: {
    bg: "#1e1e1e",
    bgStrong: "#252526",
    panel: "#252526",
    panelStrong: "#2d2d30",
    ink: "#d4d4d4",
    muted: "#9da3ab",
    line: "rgba(255, 255, 255, 0.08)",
    lineStrong: "rgba(255, 255, 255, 0.14)",
    accent: "#4ea1ff",
    accentDeep: "#2b7cd3",
    accentSoft: "#163857",
    sage: "#77c59d",
    user: "#223042",
  },
  graphite_dark: {
    bg: "#141618",
    bgStrong: "#1b1f22",
    panel: "#1a1e21",
    panelStrong: "#22282d",
    ink: "#eef2f6",
    muted: "#a0a8b3",
    line: "rgba(255, 255, 255, 0.08)",
    lineStrong: "rgba(255, 255, 255, 0.16)",
    accent: "#d28a47",
    accentDeep: "#9f6130",
    accentSoft: "#3a2a1d",
    sage: "#88b9a5",
    user: "#2c2f33",
  },
  midnight_dark: {
    bg: "#0f1722",
    bgStrong: "#16202d",
    panel: "#152131",
    panelStrong: "#1b293b",
    ink: "#e8f0fa",
    muted: "#97a8bd",
    line: "rgba(255, 255, 255, 0.08)",
    lineStrong: "rgba(255, 255, 255, 0.16)",
    accent: "#60a5fa",
    accentDeep: "#3477c9",
    accentSoft: "#1a3553",
    sage: "#75b89f",
    user: "#233247",
  },
  amber_dark: {
    bg: "#17120d",
    bgStrong: "#211911",
    panel: "#221a12",
    panelStrong: "#2c2117",
    ink: "#f5eadf",
    muted: "#b4a698",
    line: "rgba(255, 255, 255, 0.08)",
    lineStrong: "rgba(255, 255, 255, 0.14)",
    accent: "#d28a47",
    accentDeep: "#9f6130",
    accentSoft: "#3a2a1d",
    sage: "#8bb39f",
    user: "#34271d",
  },
};

const PROVIDER_TEMPLATES = {
  openai: {
    label: "OpenAI",
    provider_type: "openai",
    model_id: "gpt-5.2",
    auth_mode: "env_var",
    secret_ref: "OPENAI_API_KEY",
    base_url: "https://api.openai.com/v1",
    display_name: "OpenAI GPT",
    id_prefix: "openai",
    capabilities: ["chat", "reasoning"],
  },
  anthropic: {
    label: "Anthropic",
    provider_type: "anthropic",
    model_id: "claude-sonnet-4-5",
    auth_mode: "env_var",
    secret_ref: "ANTHROPIC_API_KEY",
    base_url: "https://api.anthropic.com/v1",
    display_name: "Anthropic Claude Sonnet",
    id_prefix: "anthropic",
    capabilities: ["chat", "reasoning"],
  },
  google_gemini: {
    label: "Google Gemini",
    provider_type: "google_gemini",
    model_id: "gemini-2.5-flash",
    auth_mode: "env_var",
    secret_ref: "GEMINI_API_KEY",
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
    display_name: "Google Gemini Flash",
    id_prefix: "gemini",
    capabilities: ["chat", "vision"],
  },
  ollama: {
    label: "Ollama Local",
    provider_type: "ollama",
    model_id: "llama3:latest",
    auth_mode: "none",
    secret_ref: "",
    base_url: "http://localhost:11434",
    display_name: "Ollama Local Llama",
    id_prefix: "ollama",
    capabilities: ["chat"],
  },
  openai_compatible: {
    label: "OpenAI Compatible",
    provider_type: "openai_compatible",
    model_id: "custom-model-id",
    auth_mode: "env_var",
    secret_ref: "COMPATIBLE_API_KEY",
    base_url: "https://example-openai-compatible.local/v1",
    display_name: "Custom OpenAI-compatible",
    id_prefix: "compatible",
    capabilities: ["chat"],
  },
  openrouter: {
    label: "OpenRouter",
    provider_type: "openrouter",
    model_id: "anthropic/claude-sonnet-4.5",
    auth_mode: "env_var",
    secret_ref: "OPENROUTER_API_KEY",
    base_url: "https://openrouter.ai/api/v1",
    display_name: "OpenRouter Claude Sonnet",
    id_prefix: "openrouter",
    capabilities: ["chat", "reasoning"],
  },
  together: {
    label: "Together",
    provider_type: "together",
    model_id: "openai/gpt-oss-20b",
    auth_mode: "env_var",
    secret_ref: "TOGETHER_API_KEY",
    base_url: "https://api.together.xyz/v1",
    display_name: "Together GPT OSS",
    id_prefix: "together",
    capabilities: ["chat", "reasoning"],
  },
  groq: {
    label: "Groq",
    provider_type: "groq",
    model_id: "openai/gpt-oss-20b",
    auth_mode: "env_var",
    secret_ref: "GROQ_API_KEY",
    base_url: "https://api.groq.com/openai/v1",
    display_name: "Groq GPT OSS",
    id_prefix: "groq",
    capabilities: ["chat", "reasoning"],
  },
  mistral: {
    label: "Mistral",
    provider_type: "mistral",
    model_id: "mistral-large-latest",
    auth_mode: "env_var",
    secret_ref: "MISTRAL_API_KEY",
    base_url: "https://api.mistral.ai/v1",
    display_name: "Mistral Large",
    id_prefix: "mistral",
    capabilities: ["chat", "reasoning"],
  },
  lm_studio: {
    label: "LM Studio",
    provider_type: "lm_studio",
    model_id: "local-model",
    auth_mode: "none",
    secret_ref: "",
    base_url: "http://localhost:1234/v1",
    display_name: "LM Studio Local",
    id_prefix: "lm-studio",
    capabilities: ["chat"],
  },
  nvidia_nim: {
    label: "NVIDIA NIM / NVIDIA Build",
    provider_type: "nvidia_nim",
    model_id: "z-ai/glm4.7",
    auth_mode: "env_var",
    secret_ref: "NVIDIA_API_KEY",
    base_url: "https://integrate.api.nvidia.com/v1",
    display_name: "NVIDIA NIM GLM",
    id_prefix: "nvidia",
    capabilities: ["chat", "planner", "tool_calling"],
  },
  cohere: {
    label: "Cohere",
    provider_type: "cohere",
    model_id: "command-a-03-2025",
    auth_mode: "env_var",
    secret_ref: "COHERE_API_KEY",
    base_url: "https://api.cohere.com/v2",
    display_name: "Cohere Command A",
    id_prefix: "cohere",
    capabilities: ["chat", "embeddings"],
  },
  huggingface: {
    label: "Hugging Face",
    provider_type: "huggingface",
    model_id: "openai/gpt-oss-120b",
    auth_mode: "env_var",
    secret_ref: "HF_TOKEN",
    base_url: "https://router.huggingface.co/v1",
    display_name: "Hugging Face Router GPT OSS",
    id_prefix: "hf",
    capabilities: ["chat", "reasoning"],
  },
};

const dom = {
  datasetToday: document.querySelector("#dataset-today"),
  statusBanner: document.querySelector("#status-banner"),
  chatWorkspace: document.querySelector("#chat-workspace"),
  sessionsPane: document.querySelector("#sessions-pane"),
  sidebarResizer: document.querySelector("#sidebar-resizer"),
  composerResizer: document.querySelector("#composer-resizer"),
  workspaceBottomResizer: document.querySelector("#workspace-bottom-resizer"),
  sessionsList: document.querySelector("#sessions-list"),
  sessionCount: document.querySelector("#session-count"),
  sessionSearch: document.querySelector("#session-search"),
  sessionFilterButtons: Array.from(document.querySelectorAll("[data-session-filter]")),
  messages: document.querySelector("#messages"),
  chatTitle: document.querySelector("#chat-title"),
  providerSelect: document.querySelector("#provider-select"),
  chatProviderSummary: document.querySelector("#chat-provider-summary"),
  chatGatingSummary: document.querySelector("#chat-gating-summary"),
  questionInput: document.querySelector("#question-input"),
  commandMenu: document.querySelector("#command-menu"),
  composerForm: document.querySelector("#composer-form"),
  sendButton: document.querySelector("#send-button"),
  retryButton: document.querySelector("#retry-button"),
  stopButton: document.querySelector("#stop-button"),
  renameSessionButton: document.querySelector("#rename-session-button"),
  deleteSessionButton: document.querySelector("#delete-session-button"),
  copySessionButton: document.querySelector("#copy-session-button"),
  sourcesButton: document.querySelector("#sources-button"),
  sourcesCount: document.querySelector("#sources-count"),
  traceVisibilityNote: document.querySelector("#trace-visibility-note"),
  activeSessionMeta: document.querySelector("#active-session-meta"),
  tabButtons: Array.from(document.querySelectorAll(".navlink[data-view]")),
  views: {
    chat: document.querySelector("#view-chat"),
    settings: document.querySelector("#view-settings"),
  },
  subtabButtons: Array.from(document.querySelectorAll(".subtab")),
  subviews: Array.from(document.querySelectorAll(".subview")),
  newSessionButton: document.querySelector("#new-session-button"),
  appearanceForm: document.querySelector("#appearance-form"),
  appearanceThemeMode: document.querySelector("#appearance-theme-mode"),
  appearanceLightTheme: document.querySelector("#appearance-light-theme"),
  appearanceDarkTheme: document.querySelector("#appearance-dark-theme"),
  uiSettingsForm: document.querySelector("#ui-settings-form"),
  defaultGating: document.querySelector("#settings-default-gating"),
  verboseTrace: document.querySelector("#settings-verbose-trace"),
  providerTemplateSelect: document.querySelector("#provider-template-select"),
  providerApplyTemplate: document.querySelector("#provider-apply-template"),
  providersForm: document.querySelector("#providers-form"),
  providerFormModePill: document.querySelector("#provider-form-mode-pill"),
  providerDisplayName: document.querySelector("#provider-display-name"),
  providerType: document.querySelector("#provider-type"),
  providerAuthMode: document.querySelector("#provider-auth-mode"),
  providerSecretRefLabel: document.querySelector("#provider-secret-ref-label"),
  providerSecretRef: document.querySelector("#provider-secret-ref"),
  providerSecretValueRow: document.querySelector("#provider-secret-value-row"),
  providerSecretValue: document.querySelector("#provider-secret-value"),
  providerBaseUrl: document.querySelector("#provider-base-url"),
  providerModelId: document.querySelector("#provider-model-id"),
  providerContextWindow: document.querySelector("#provider-context-window"),
  providerCapabilities: document.querySelector("#provider-capabilities"),
  providerEnabled: document.querySelector("#provider-enabled"),
  providerSaveDraft: document.querySelector("#provider-save-draft"),
  providerCheckDraft: document.querySelector("#provider-check-draft"),
  providerNew: document.querySelector("#provider-new"),
  providerCancelEdit: document.querySelector("#provider-cancel-edit"),
  providerFormStatus: document.querySelector("#provider-form-status"),
  providersRegistryPill: document.querySelector("#providers-registry-pill"),
  providerAddExamples: document.querySelector("#provider-add-examples"),
  providersRegistry: document.querySelector("#providers-registry"),
  intentPrimary: document.querySelector("#intent-primary"),
  intentFallbacks: document.querySelector("#intent-fallbacks"),
  synthesisPrimary: document.querySelector("#synthesis-primary"),
  synthesisFallbacks: document.querySelector("#synthesis-fallbacks"),
  configExportButton: document.querySelector("#config-export-button"),
  configLoadCurrent: document.querySelector("#config-load-current"),
  configImportForm: document.querySelector("#config-import-form"),
  configImportFile: document.querySelector("#config-import-file"),
  configImportText: document.querySelector("#config-import-text"),
  configImportFeedback: document.querySelector("#config-import-feedback"),
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
  window.addEventListener("beforeunload", persistUIState);
  window.addEventListener("scroll", queuePersistUIState, { passive: true });
  window.addEventListener("hashchange", handleHashNavigation);
  initializeWorkspaceResizers();
  dom.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  dom.subtabButtons.forEach((button) => {
    button.addEventListener("click", () => setSubtab(button.dataset.subtab));
  });
  dom.sessionFilterButtons.forEach((button) => {
    button.addEventListener("click", () => setSessionFilter(button.dataset.sessionFilter));
  });
  dom.newSessionButton.addEventListener("click", () => createSession(true));
  dom.sessionSearch.addEventListener("input", () => {
    state.sessionSearch = dom.sessionSearch.value.trim();
    renderSessions();
    queuePersistUIState();
  });
  dom.appearanceForm.addEventListener("change", () => {
    saveAppearance().catch((error) => {
      console.error(error);
      setStatus(error.message || "Saving appearance failed.");
    });
  });
  dom.providerSelect.addEventListener("change", () => {
    state.selectedProviderId = dom.providerSelect.value;
    updateChatControlSummaries();
    queuePersistUIState();
  });
  dom.retryButton.addEventListener("click", () => {
    retryLastTurn().catch((error) => {
      console.error(error);
      setStatus(error.message || "Retry failed.");
    });
  });
  dom.stopButton.addEventListener("click", () => {
    stopStreaming();
  });
  dom.renameSessionButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    renameCurrentSession().catch((error) => {
      console.error(error);
      setStatus(error.message || "Rename failed.");
    });
  });
  dom.deleteSessionButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    deleteCurrentSession().catch((error) => {
      console.error(error);
      setStatus(error.message || "Delete failed.");
    });
  });
  dom.copySessionButton.addEventListener("click", () => {
    copyCurrentTranscript().catch((error) => {
      console.error(error);
      setStatus(error.message || "Copy failed.");
    });
  });
  dom.sourcesButton.addEventListener("click", () => {
    setView("settings");
    setSubtab("providers");
  });
  dom.messages.addEventListener("click", (event) => {
    const promptButton = event.target.closest("[data-prompt]");
    if (!promptButton) {
      const actionButton = event.target.closest("[data-message-action]");
      if (!actionButton) {
        return;
      }
      handleMessageAction(actionButton.dataset.messageAction, Number(actionButton.dataset.messageIndex)).catch((error) => {
        console.error(error);
        setStatus(error.message || "Message action failed.");
      });
      return;
    }
    dom.questionInput.value = promptButton.dataset.prompt || "";
    dom.questionInput.focus();
  });
  dom.questionInput.addEventListener("keydown", (event) => {
    if (handleCommandMenuKeydown(event)) {
      return;
    }
    if (event.key !== "Enter" || event.isComposing) {
      return;
    }
    if (event.ctrlKey) {
      return;
    }
    event.preventDefault();
    if (state.isSending) {
      return;
    }
    sendMessage().catch((error) => {
      console.error(error);
      setStatus(error.message || "Chat request failed.");
      state.isSending = false;
      renderMessages();
      updateComposerState();
    });
  });
  dom.questionInput.addEventListener("input", () => {
    syncCommandMenu();
  });
  dom.questionInput.addEventListener("blur", () => {
    window.setTimeout(() => {
      hideCommandMenu();
    }, 120);
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
  dom.providerApplyTemplate.addEventListener("click", () => {
    startProviderDraft(dom.providerTemplateSelect.value);
    setProviderFormStatus(`Applied ${dom.providerTemplateSelect.options[dom.providerTemplateSelect.selectedIndex]?.text || "template"}. Save Provider is still required.`);
  });
  dom.providerAuthMode.addEventListener("change", () => {
    updateProviderAuthFields();
  });
  dom.providerSaveDraft.addEventListener("click", () => {
    saveProviderSettings().catch((error) => {
      console.error(error);
      setProviderFormStatus(error.message || "Saving provider failed.", true);
      setStatus(error.message || "Saving provider failed.");
    });
  });
  dom.providerCheckDraft.addEventListener("click", () => {
    try {
      validateProviderDraft(readProviderEditorForm());
      setProviderFormStatus("Draft looks valid for this app's provider config.");
      setStatus("Provider draft check passed");
    } catch (error) {
      setProviderFormStatus(error.message || "Draft check failed.", true);
      setStatus(error.message || "Draft check failed.");
    }
  });
  dom.providerNew.addEventListener("click", () => {
    startProviderDraft(dom.providerTemplateSelect.value);
    setProviderFormStatus("New provider form ready.");
  });
  dom.providerCancelEdit.addEventListener("click", () => {
    resetProviderDraft();
    renderProviderSettings();
    setProviderFormStatus("Provider editor reset.");
  });
  dom.providerAddExamples.addEventListener("click", () => {
    addMissingExampleProviders();
  });
  dom.providersRegistry.addEventListener("click", (event) => {
    handleProviderRegistryAction(event).catch((error) => {
      console.error(error);
      setStatus(error.message || "Provider action failed.");
    });
  });
  dom.providersForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveProviderSettings().catch((error) => {
      console.error(error);
      setStatus(error.message || "Saving provider settings failed.");
    });
  });
  dom.configExportButton.addEventListener("click", () => {
    exportConfigPayload().catch((error) => {
      console.error(error);
      setStatus(error.message || "Export failed.");
      setConfigFeedback(error.message || "Export failed.", true);
    });
  });
  dom.configLoadCurrent.addEventListener("click", () => {
    loadCurrentConfigIntoEditor().catch((error) => {
      console.error(error);
      setStatus(error.message || "Loading current config failed.");
      setConfigFeedback(error.message || "Loading current config failed.", true);
    });
  });
  dom.configImportFile.addEventListener("change", () => {
    loadSelectedConfigFile().catch((error) => {
      console.error(error);
      setConfigFeedback(error.message || "Reading config file failed.", true);
    });
  });
  dom.configImportForm.addEventListener("submit", (event) => {
    event.preventDefault();
    importConfigPayload().catch((error) => {
      console.error(error);
      setStatus(error.message || "Import failed.");
      setConfigFeedback(error.message || "Import failed.", true);
    });
  });
  dom.sessionsList.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-session-action]");
    if (!actionButton) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const sessionId = actionButton.dataset.sessionId || "";
    handleSessionListAction(actionButton.dataset.sessionAction, sessionId).catch((error) => {
      console.error(error);
      setStatus(error.message || "Session action failed.");
    });
  });
}

async function initialize() {
  setStatus("Loading workspace");
  const storedUIState = readStoredUIState();
  const hashUIState = readHashUIState();
  const [health, sessions, providersPayload, ui, appearance, commandsPayload] = await Promise.all([
    api("/health"),
    api("/api/sessions"),
    api("/api/settings/providers"),
    api("/api/settings/ui"),
    api("/api/settings/appearance"),
    api("/api/chat/commands"),
  ]);
  state.health = health;
  state.sessions = sessions.sessions || [];
  state.providers = providersPayload.llm_providers || [];
  state.modelRouting = providersPayload.model_routing || {};
  state.ui = ui;
  state.appearance = readStoredAppearance() || appearance;
  state.commands = commandsPayload.commands || [];
  state.selectedProviderId = resolveStoredProviderSelection(storedUIState?.selectedProviderId);
  state.gatingMode = "bind_all";
  state.sessionFilter = storedUIState?.sessionFilter === "archived" ? "archived" : "active";
  state.sessionSearch = String(storedUIState?.sessionSearch || "");
  state.archivedSessionIds = new Set(Array.isArray(storedUIState?.archivedSessionIds) ? storedUIState.archivedSessionIds : []);
  state.sidebarWidth = clampSidebarWidth(storedUIState?.sidebarWidth);
  state.workspaceHeight = clampWorkspaceHeight(storedUIState?.workspaceHeight);
  state.totalWorkspaceHeight = clampTotalWorkspaceHeight(storedUIState?.totalWorkspaceHeight);
  state.providerSort = resolveStoredProviderSort(storedUIState?.providerSort);
  restoreProviderEditorState(storedUIState?.providerEditor);

  renderHealth();
  renderProviderTemplateOptions();
  ensureProviderDraft();
  applyWorkspaceLayout();
  renderSessions();
  renderProviderControls();
  renderProviderSettings();
  renderUISettings();
  renderAppearance();
  applyAppearance();
  updateTraceNote();
  updateActiveSessionMeta();
  updateComposerState();
  updateChatControlSummaries();
  renderSessionFilters();
  applyStoredNavigation(hashUIState, storedUIState);

  const initialSessionId = resolveInitialSessionId(storedUIState?.sessionId);
  if (initialSessionId) {
    await openSession(initialSessionId);
  } else if (state.sessions.length > 0) {
    await openSession(state.sessions[0].id);
  } else {
    renderMessages();
  }

  restoreScrollPosition(storedUIState?.scrollY);
  persistUIState();
  setStatus("Ready");
}

function renderHealth() {
  dom.datasetToday.textContent = state.health?.dataset_today || "Unknown";
  updateSourcesCount();
}

function renderSessions() {
  dom.sessionsList.innerHTML = "";
  dom.sessionSearch.value = state.sessionSearch;
  const filteredSessions = getVisibleSessions();
  dom.sessionCount.textContent = `${filteredSessions.length} chat${filteredSessions.length === 1 ? "" : "s"}`;
  if (filteredSessions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "session-empty";
    empty.innerHTML = state.sessionFilter === "archived"
      ? "<strong>No archived chats</strong><span>Archive chats from the active list to keep them here.</span>"
      : "<strong>No chats yet</strong><span>Create one to begin.</span>";
    dom.sessionsList.appendChild(empty);
    return;
  }
  filteredSessions.forEach((session) => {
    const article = document.createElement("article");
    article.className = `session-item${session.id === state.sessionId ? " is-active" : ""}`;
    const isArchived = state.archivedSessionIds.has(session.id);
    article.innerHTML = `
      <div class="session-item-top">
        <button class="session-open session-title-button" type="button" data-session-action="open" data-session-id="${escapeAttr(session.id)}">
          <strong>${escapeHtml(session.title || "New chat")}</strong>
        </button>
        <div class="session-item-badges">
          <span class="session-badge">${Number(session.message_count || 0)}</span>
          <button class="icon-button icon-button-xs" type="button" data-session-action="${isArchived ? "unarchive" : "archive"}" data-session-id="${escapeAttr(session.id)}" title="${isArchived ? "Restore chat" : "Archive chat"}" aria-label="${isArchived ? "Restore chat" : "Archive chat"}">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h18v4H3V5Zm2 6h14v8H5v-8Zm3 2v2h8v-2H8Z"/></svg>
          </button>
          <button class="icon-button icon-button-xs" type="button" data-session-action="delete" data-session-id="${escapeAttr(session.id)}" title="Delete chat" aria-label="Delete chat">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 21a2 2 0 0 1-2-2V7h14v12a2 2 0 0 1-2 2H7Zm10-12H7v10h10V9ZM15 4V3H9v1H4v2h16V4h-5Z"/></svg>
          </button>
        </div>
      </div>
      <button class="session-open" type="button" data-session-action="open" data-session-id="${escapeAttr(session.id)}">
        <span class="session-item-meta">${escapeHtml(formatSessionSummary(session))}</span>
        <span class="session-item-preview">${escapeHtml(buildSessionPreview(session))}</span>
      </button>
      <div class="session-item-footer">
        <span class="session-item-id-label">session id</span>
        <code class="session-item-id" title="${escapeAttr(session.id)}">${escapeHtml(session.id)}</code>
      </div>
    `;
    dom.sessionsList.appendChild(article);
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
  state.messageTraceOpen = {};
  if (state.sessionFilter === "archived") {
    state.sessionFilter = "active";
  }
  renderSessions();
  renderSessionFilters();
  updateActiveSessionMeta();
  renderMessages();
  if (focusChat) {
    setView("chat");
    dom.questionInput.focus();
  }
  queuePersistUIState();
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
  state.messageTraceOpen = {};
  renderSessions();
  updateActiveSessionMeta();
  renderMessages();
  queuePersistUIState();
  setStatus(`Opened "${session.title || "New chat"}"`);
}

function renderMessages() {
  dom.messages.innerHTML = "";
  if (state.messages.length === 0) {
    dom.messages.appendChild(dom.emptyStateTemplate.content.cloneNode(true));
    return;
  }
  state.messages.forEach((message, index) => {
    dom.messages.appendChild(renderMessageCard(message, index));
  });
  dom.messages.scrollTop = dom.messages.scrollHeight;
}

function renderMessageCard(message, index) {
  const article = document.createElement("article");
  const isPendingAssistant = isAssistantMessagePending(message);
  article.className = `message-card ${message.role}${isPendingAssistant ? " is-pending" : ""}`;

  const head = document.createElement("div");
  head.className = "message-head";
  const label = message.role === "assistant" ? buildAssistantLabel(message) : "You";
  const actions = message.role === "assistant"
    ? `
      <div class="message-actions">
        <button class="icon-button icon-button-xs" type="button" data-message-action="retry" data-message-index="${index}" title="Retry from last user prompt" aria-label="Retry from last user prompt">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v4H4l5 5 5-5h-4V5H8Zm8 10v4h-4l5 5 5-5h-4v-4h-2Zm-7.5 1.5L4 12l1.5-1.5L10 15l-1.5 1.5Z"/></svg>
        </button>
        <button class="icon-button icon-button-xs" type="button" data-message-action="copy" data-message-index="${index}" title="Copy message" aria-label="Copy message">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H6a2 2 0 0 0-2 2v12h2V3h10V1Zm3 4H10a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Zm0 16H10V7h9v14Z"/></svg>
        </button>
      </div>
    `
    : `<button class="message-text-button" type="button" data-message-action="resend" data-message-index="${index}">Resend</button>`;
  head.innerHTML = `
    <div class="message-role-row">
      <div class="message-role">${escapeHtml(label)}</div>
    </div>
    <div class="message-head-meta">
      ${actions}
      <div class="message-time">${formatTime(message.metadata?.telemetry?.finished_at || message.created_at)}</div>
    </div>
  `;

  const body = document.createElement("div");
  body.className = "message-content";
  body.innerHTML = isPendingAssistant
    ? renderPendingAssistantMessage(message)
    : renderMarkdown(message.content || "");
  article.append(head, body);

  if (message.role === "assistant") {
    const metadata = message.metadata || {};
    if (state.ui.verbose_trace && shouldRenderAgentActivity(metadata)) {
      article.appendChild(renderAgentActivity(metadata, message, index));
    }

    if (metadata.telemetry) {
      article.appendChild(renderMetaRow(metadata));
    }
  }

  return article;
}

function renderMetaRow(metadata) {
  const telemetry = metadata.telemetry || {};
  const totalUsage = selectUsageSnapshot(telemetry);
  const elapsedMs = selectElapsedMs(metadata, telemetry);
  const iterations = Number(metadata.iterations || 0);
  const toolCalls = Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [];
  const fastPath = String(metadata.fast_path || "").trim();
  const hasUsage = totalUsage.input_tokens > 0 || totalUsage.output_tokens > 0 || totalUsage.total_tokens > 0;
  const hasRuntimeStats = elapsedMs > 0 || hasUsage || iterations > 0;
  const row = document.createElement("div");
  row.className = "meta-row";
  if (!hasRuntimeStats) {
    row.innerHTML = `<span>${escapeHtml(renderFastPathLabel(fastPath))}</span>`;
    return row;
  }

  const parts = [];
  if (telemetry.intent_model) {
    parts.push(escapeHtml(telemetry.intent_model));
  } else if (metadata.provider_id) {
    parts.push(escapeHtml(metadata.provider_id));
  }
  if (telemetry.synthesis_model) {
    parts.push(escapeHtml(telemetry.synthesis_model));
  }
  if (elapsedMs > 0) {
    parts.push(`${elapsedMs} ms`);
  }
  if (hasUsage) {
    parts.push(`↑${formatCompactNumber(totalUsage.input_tokens)}`);
    parts.push(`↓${formatCompactNumber(totalUsage.output_tokens)} tok`);
    const throughput = formatTokenThroughput(totalUsage.output_tokens, elapsedMs);
    if (throughput) {
      parts.push(`${throughput} tok/s`);
    }
  }
  if (iterations > 0) {
    parts.push(`${iterations} iter`);
  }
  if (toolCalls.length > 0) {
    parts.push("[tool_calls]");
  }
  row.innerHTML = parts.map((part) => `<span>${part}</span>`).join('<span>·</span>');
  return row;
}

function shouldRenderAgentActivity(metadata) {
  const traceEvents = Array.isArray(metadata.trace_events) ? metadata.trace_events : [];
  const toolCalls = Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [];
  const hasIteratedTrace = traceEvents.some((event) => Number(event.iteration || 0) > 0);
  return toolCalls.length > 0 || hasIteratedTrace || Number(metadata.iterations || 0) > 0;
}

function renderAgentActivity(metadata, message, index) {
  const activity = buildAgentActivityModel(metadata);
  const section = document.createElement("details");
  section.className = "message-trace";
  section.dataset.messageIndex = String(index);
  section.open = isAgentActivityOpen(message, index);
  section.addEventListener("toggle", () => {
    setAgentActivityOpen(message, index, section.open);
  });
  section.innerHTML = `
    <summary class="message-trace-summary">
      <span>Agent activity</span>
      <span class="message-trace-summary-meta">
        <span class="trace-status-pill${activity.pending ? " is-running" : ""}">${escapeHtml(activity.pending ? "RUNNING" : "COMPLETE")}</span>
        <span>${activity.iterations.length} iteration${activity.iterations.length === 1 ? "" : "s"} · ${activity.toolCount} tool${activity.toolCount === 1 ? "" : "s"}</span>
      </span>
    </summary>
  `;

  const content = document.createElement("div");
  content.className = "trace-list";

  const runRow = document.createElement("div");
  runRow.className = "trace-run-row";
  runRow.innerHTML = `<span class="trace-run-dot"></span><span>Agent run</span>`;
  content.appendChild(runRow);

  activity.iterations.forEach((iteration) => {
    const iterationBlock = document.createElement("section");
    iterationBlock.className = "trace-iteration";
    iterationBlock.innerHTML = `
      <div class="trace-iteration-title">
        <span class="trace-run-dot"></span>
        <span>Iteration ${iteration.number}</span>
      </div>
    `;

    const toolsWrap = document.createElement("div");
    toolsWrap.className = "trace-tool-list";
    if (iteration.tools.length === 0) {
      const empty = document.createElement("div");
      empty.className = "trace-empty";
      empty.textContent = "no tools";
      toolsWrap.appendChild(empty);
    } else {
      iteration.tools.forEach((tool) => {
        const item = document.createElement("div");
        item.className = `trace-tool-card${tool.pending ? " is-pending" : ""}`;
        item.innerHTML = `
          <div class="trace-tool-dot"></div>
          <div class="trace-tool-name">${escapeHtml(tool.name || "tool")}</div>
          <div class="trace-tool-meta">${escapeHtml(formatActivityToolMeta(tool))}</div>
        `;
        toolsWrap.appendChild(item);
      });
    }
    iterationBlock.appendChild(toolsWrap);
    content.appendChild(iterationBlock);
  });

  const doneRow = document.createElement("div");
  doneRow.className = "trace-done-row";
  doneRow.innerHTML = `
    <span class="trace-run-dot"></span>
    <span>Done · ${escapeHtml(activity.stopReason)}</span>
  `;
  content.appendChild(doneRow);

  section.appendChild(content);
  return section;
}

function buildAgentActivityModel(metadata) {
  const toolCalls = Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [];
  const traceEvents = Array.isArray(metadata.trace_events) ? metadata.trace_events : [];
  const pending = Boolean(metadata.pending);
  const traceIterations = traceEvents
    .map((event) => Number(event.iteration || 0))
    .filter((value) => value > 0);
  const toolIterations = toolCalls
    .map((call) => Number(call.iteration || 0))
    .filter((value) => value > 0);
  const maxIteration = Math.max(
    Number(metadata.iterations || 0),
    traceIterations.length ? Math.max(...traceIterations) : 0,
    toolIterations.length ? Math.max(...toolIterations) : 0,
  );
  const finalTools = groupCompletedToolsByIteration(toolCalls);
  const liveTools = groupLiveToolsByIteration(traceEvents);
  const iterations = [];
  let toolCount = 0;

  for (let iteration = 1; iteration <= Math.max(maxIteration, 1); iteration += 1) {
    const tools = finalTools.get(iteration) || liveTools.get(iteration) || [];
    toolCount += tools.length;
    iterations.push({ number: iteration, tools });
  }

  return {
    pending,
    iterations,
    toolCount,
    stopReason: normalizeStopReason(metadata.stop_reason || inferStopReason(metadata)),
  };
}

function groupCompletedToolsByIteration(toolCalls) {
  const grouped = new Map();
  toolCalls.forEach((call) => {
    const iteration = Number(call.iteration || 0);
    if (iteration <= 0) {
      return;
    }
    if (!grouped.has(iteration)) {
      grouped.set(iteration, []);
    }
    grouped.get(iteration).push({
      name: call.name || "",
      args: call.args && typeof call.args === "object" ? call.args : {},
      result: call.result && typeof call.result === "object" ? call.result : {},
      latencyMs: Number(call.latency_ms || 0),
      pending: false,
    });
  });
  return grouped;
}

function groupLiveToolsByIteration(traceEvents) {
  const grouped = new Map();
  const pendingByIteration = new Map();
  traceEvents.forEach((event) => {
    const iteration = Number(event.iteration || 0);
    if (iteration <= 0) {
      return;
    }
    if (!grouped.has(iteration)) {
      grouped.set(iteration, []);
      pendingByIteration.set(iteration, new Map());
    }
    const pendingTools = pendingByIteration.get(iteration);
    if (event.kind === "tool_started") {
      const tool = {
        name: event.tool_name || "",
        args: event.details && typeof event.details.args === "object" ? event.details.args : {},
        result: {},
        latencyMs: 0,
        pending: true,
      };
      grouped.get(iteration).push(tool);
      pendingTools.set(event.tool_name || `${grouped.get(iteration).length}`, tool);
      return;
    }
    if (event.kind === "tool_finished") {
      const tool = pendingTools.get(event.tool_name || "");
      if (tool) {
        tool.latencyMs = Number(event.latency_ms || 0);
        tool.pending = false;
      }
    }
  });
  return grouped;
}

function formatActivityToolMeta(tool) {
  const parts = [];
  Object.entries(tool.args || {}).slice(0, 2).forEach(([key, value]) => {
    parts.push(`${key}: ${summarizeActivityValue(value)}`);
  });
  const resultKeys = Object.keys(tool.result || {});
  if (resultKeys.length > 0) {
    parts.push(resultKeys.slice(0, 4).join(", "));
  }
  if (tool.pending) {
    parts.push("running");
  }
  if (tool.latencyMs > 0) {
    parts.push(`${tool.latencyMs} ms`);
  }
  return parts.join(" · ");
}

function summarizeActivityValue(value) {
  if (Array.isArray(value)) {
    return value.length === 0 ? "[]" : `${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (value && typeof value === "object") {
    return "object";
  }
  const text = String(value ?? "").trim();
  if (!text) {
    return "empty";
  }
  return text.length > 72 ? `${text.slice(0, 69)}...` : text;
}

function inferStopReason(metadata) {
  if (metadata.fast_path) {
    return metadata.fast_path;
  }
  const iterations = Number(metadata.iterations || 0);
  const toolCalls = Array.isArray(metadata.tool_calls) ? metadata.tool_calls : [];
  if (iterations > 0 && toolCalls.length < iterations) {
    return "final_answer";
  }
  return "complete";
}

function normalizeStopReason(reason) {
  return String(reason || "complete").trim().toLowerCase().replaceAll(" ", "_");
}

function selectUsageSnapshot(telemetry) {
  const totalUsage = telemetry.total_usage;
  if (totalUsage && typeof totalUsage === "object") {
    return {
      input_tokens: Number(totalUsage.input_tokens || 0),
      output_tokens: Number(totalUsage.output_tokens || 0),
      total_tokens: Number(totalUsage.total_tokens || 0),
    };
  }
  return {
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  };
}

function selectElapsedMs(metadata, telemetry) {
  const telemetryElapsed = Number(telemetry.elapsed_ms || 0);
  if (telemetryElapsed > 0) {
    return telemetryElapsed;
  }
  const intentLatency = Number(metadata.intent_meta?.latency_ms || 0);
  if (intentLatency > 0) {
    return intentLatency;
  }
  return 0;
}

function renderFastPathLabel(fastPath) {
  if (fastPath === "smalltalk") {
    return "Smalltalk fast-path (no model call)";
  }
  if (fastPath) {
    return `${fastPath} fast-path`;
  }
  return "No runtime statistics recorded";
}

function renderProviderControls() {
  dom.providerSelect.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = defaultProviderOptionLabel();
  dom.providerSelect.appendChild(defaultOption);
  state.providers.forEach((provider) => {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent = `${provider.display_name} (${provider.model_id})`;
    dom.providerSelect.appendChild(option);
  });
  if (state.selectedProviderId && !state.providers.some((provider) => provider.id === state.selectedProviderId)) {
    state.selectedProviderId = "";
  }
  dom.providerSelect.value = state.selectedProviderId;
  updateChatControlSummaries();
  updateSourcesCount();
}

function renderUISettings() {
  dom.defaultGating.value = state.ui.default_gating_mode || "gated";
  dom.verboseTrace.checked = Boolean(state.ui.verbose_trace);
}

function renderProviderTemplateOptions() {
  dom.providerTemplateSelect.innerHTML = Object.entries(PROVIDER_TEMPLATES)
    .map(([key, template]) => `<option value="${escapeAttr(key)}">${escapeHtml(template.label)}</option>`)
    .join("");
  dom.providerType.innerHTML = providerTypeOptions("");
  dom.providerAuthMode.innerHTML = authModeOptions("");
}

function ensureProviderDraft() {
  if (state.providerEditor.draft) {
    return;
  }
  if (state.providers.length > 0) {
    selectProvider(state.providerEditor.selectedIndex >= 0 ? state.providerEditor.selectedIndex : 0);
    return;
  }
  state.providerEditor = {
    selectedIndex: -1,
    draft: makeBlankProvider(),
    isNew: true,
  };
}

function renderProviderSettings() {
  ensureProviderDraft();
  renderProviderForm();
  renderProviderRegistry();
  renderRoutingControls();
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

function renderProviderForm() {
  const draft = state.providerEditor.draft || makeBlankProvider();
  dom.providerFormModePill.textContent = state.providerEditor.isNew ? "New provider" : "Editing selected";
  dom.providerFormModePill.className = `panel-pill${state.providerEditor.isNew ? "" : " panel-pill-warn"}`;
  dom.providerDisplayName.value = draft.display_name || "";
  dom.providerType.innerHTML = providerTypeOptions(draft.provider_type);
  dom.providerAuthMode.innerHTML = authModeOptions(draft.auth_mode);
  dom.providerSecretRef.value = draft.secret_ref || "";
  dom.providerBaseUrl.value = draft.base_url || "";
  dom.providerModelId.value = draft.model_id || "";
  dom.providerContextWindow.value = draft.context_window || "";
  dom.providerCapabilities.value = Array.isArray(draft.capabilities) ? draft.capabilities.join(", ") : "";
  dom.providerEnabled.checked = draft.enabled !== false;
  dom.providerSecretValue.value = "";
  updateProviderAuthFields();
}

function renderProviderRegistry() {
  const enabledCount = state.providers.filter((provider) => provider.enabled !== false).length;
  dom.providersRegistryPill.textContent = `${enabledCount} enabled`;
  if (!state.providers.length) {
    dom.providersRegistry.innerHTML = `
      <div class="placeholder-panel provider-empty">
        <p class="eyebrow">Registry</p>
        <h2>No providers yet</h2>
        <p class="panel-note">Apply a template or start a new draft, then save it into the registry.</p>
      </div>
    `;
    return;
  }
  const direction = state.providerSort.direction === "desc" ? -1 : 1;
  const rows = state.providers
    .map((provider, index) => ({ provider, index }))
    .sort((left, right) => compareProviderRows(left.provider, right.provider, state.providerSort.key) * direction);
  dom.providersRegistry.innerHTML = `
    <table class="provider-registry-table">
      <thead>
        <tr>
          ${renderProviderSortHeader("Name", "display_name")}
          ${renderProviderSortHeader("Type", "provider_type")}
          ${renderProviderSortHeader("Model", "model_id")}
          ${renderProviderSortHeader("Auth", "auth")}
          ${renderProviderSortHeader("Capabilities", "capabilities")}
          ${renderProviderSortHeader("Enabled", "enabled")}
          ${renderProviderSortHeader("Status", "status")}
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(({ provider, index }) => renderProviderRegistryRow(provider, index)).join("")}
      </tbody>
    </table>
  `;
}

async function handleProviderRegistryAction(event) {
  const actionButton = event.target.closest("[data-action], [data-sort]");
  if (!actionButton) {
    return;
  }
  if (actionButton.dataset.sort) {
    toggleProviderSort(actionButton.dataset.sort);
    renderProviderSettings();
    queuePersistUIState();
    return;
  }
  const index = Number(actionButton.dataset.index);
  if (actionButton.dataset.action === "edit-provider") {
    selectProvider(index);
    renderProviderSettings();
    setProviderFormStatus("Loaded provider into the editor.");
    queuePersistUIState();
    return;
  }
  if (actionButton.dataset.action === "remove-provider") {
    removeProvider(index);
    renderProviderSettings();
    setProviderFormStatus("Provider removed from the local registry.");
    queuePersistUIState();
    return;
  }
  if (actionButton.dataset.action === "toggle-enabled") {
    toggleProviderEnabled(index);
    renderProviderSettings();
    queuePersistUIState();
    return;
  }
  if (actionButton.dataset.action === "set-default") {
    setChatRouteProvider(index);
    renderProviderSettings();
    setProviderFormStatus("Updated the chat route primary provider.");
    queuePersistUIState();
    return;
  }
  if (actionButton.dataset.action === "check-provider") {
    const provider = state.providers[index];
    validateProviderDraft(provider, { ignoreDuplicateId: true });
    setProviderFormStatus(`${provider.display_name || provider.id} passed local draft validation.`);
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
  state.gatingMode = "bind_all";
  renderUISettings();
  updateTraceNote();
  setStatus("Defaults saved");
}

async function saveProviderSettings() {
  commitProviderDraftFromDom();
  const pendingSecrets = new Map(
    state.providers
      .filter((provider) => provider.auth_mode === "stored_secret" && provider.secret_ref && provider._pending_secret_value)
      .map((provider) => [provider.id, { secret_ref: provider.secret_ref, value: provider._pending_secret_value }])
  );
  const providerPayload = state.providers.map((provider) => {
    const next = { ...provider };
    delete next.has_secret;
    delete next._pending_secret_value;
    return next;
  });
  const payload = {
    llm_providers: providerPayload,
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
  state.providers.forEach((provider) => {
    const pending = pendingSecrets.get(provider.id);
    if (!pending) {
      return;
    }
    provider.secret_ref = pending.secret_ref;
    provider._pending_secret_value = pending.value;
  });
  await persistPendingProviderSecrets();
  ensureProviderSelectionAfterRefresh();
  renderProviderControls();
  renderProviderSettings();
  setProviderFormStatus("Provider saved.");
  persistUIState();
  setStatus("Provider settings saved");
}

async function sendMessage() {
  const question = dom.questionInput.value.trim();
  if (!question || state.isSending) {
    return;
  }
  if (question.startsWith("/")) {
    await executeCommand(question);
    return;
  }
  state.isSending = true;
  state.lastQuestion = question;
  state.abortController = new AbortController();
  updateComposerState();
  updateTraceNote();
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
      pending: true,
      trace_events: [],
      telemetry: {},
      gating_mode: state.gatingMode,
    },
    created_at: new Date().toISOString(),
  };

  state.messages.push(userMessage, assistantMessage);
  renderMessages();
  dom.questionInput.value = "";
  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.abortController.signal,
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
        assistantMessage.metadata = {
          ...event.response,
          pending: false,
        };
        renderMessages();
        return;
      }
      if (event.type === "error") {
        assistantMessage.content = `Error: ${event.error}`;
        assistantMessage.metadata = {
          ...assistantMessage.metadata,
          error: event.error,
          pending: false,
        };
        renderMessages();
      }
    });
    setStatus("Reply complete");
  } catch (error) {
    const wasAborted = error instanceof DOMException && error.name === "AbortError";
    const message = wasAborted ? "Stopped." : (error instanceof Error ? error.message : String(error));
    assistantMessage.content = wasAborted ? message : `Error: ${message}`;
    assistantMessage.metadata = {
      ...assistantMessage.metadata,
      error: message,
      pending: false,
    };
    renderMessages();
    throw error;
  } finally {
    state.isSending = false;
    state.abortController = null;
    updateComposerState();
    updateTraceNote();
    await refreshSessions();
  }
}

async function executeCommand(commandText) {
  state.isSending = true;
  state.lastQuestion = commandText;
  hideCommandMenu();
  updateComposerState();
  updateTraceNote();
  setStatus("Running command");

  if (!state.sessionId) {
    await createSession(false);
  }

  const userMessage = {
    role: "user",
    content: commandText,
    metadata: {},
    created_at: new Date().toISOString(),
  };
  const assistantMessage = {
    role: "assistant",
    content: "Running command...",
    metadata: {
      pending: true,
      kind: "slash_command",
    },
    created_at: new Date().toISOString(),
  };

  state.messages.push(userMessage, assistantMessage);
  renderMessages();
  dom.questionInput.value = "";
  try {
    const response = await api("/api/chat/commands/execute", {
      method: "POST",
      body: JSON.stringify({
        command: commandText,
        session_id: state.sessionId,
      }),
    });
    assistantMessage.content = response.answer || "";
    assistantMessage.metadata = {
      ...(response.metadata || {}),
      pending: false,
    };
    renderMessages();
    setStatus("Command complete");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    assistantMessage.content = `Error: ${message}`;
    assistantMessage.metadata = {
      ...assistantMessage.metadata,
      error: message,
      pending: false,
    };
    renderMessages();
    throw error;
  } finally {
    state.isSending = false;
    updateComposerState();
    updateTraceNote();
    await refreshSessions();
    dom.questionInput.focus();
  }
}

async function refreshSessions() {
  const payload = await api("/api/sessions");
  state.sessions = payload.sessions || [];
  renderSessions();
  updateActiveSessionMeta();
}

function setSessionFilter(filterName) {
  state.sessionFilter = filterName === "archived" ? "archived" : "active";
  renderSessionFilters();
  renderSessions();
  queuePersistUIState();
}

function renderSessionFilters() {
  dom.sessionFilterButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.sessionFilter === state.sessionFilter);
  });
}

function updateSourcesCount() {
  const enabled = state.providers.filter((provider) => provider.enabled !== false).length;
  dom.sourcesCount.textContent = `${enabled}/${state.providers.length}`;
}

async function retryLastTurn() {
  const question = findLastUserQuestion();
  if (!question || state.isSending) {
    return;
  }
  dom.questionInput.value = question;
  await sendMessage();
}

function stopStreaming() {
  if (!state.abortController) {
    return;
  }
  state.abortController.abort();
  setStatus("Stopped");
}

async function renameCurrentSession() {
  if (!state.sessionId) {
    return;
  }
  const current = state.sessions.find((session) => session.id === state.sessionId);
  const nextTitle = window.prompt("Rename chat", current?.title || "New chat");
  if (!nextTitle || !nextTitle.trim()) {
    return;
  }
  await api(`/api/sessions/${state.sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title: nextTitle.trim() }),
  });
  await refreshSessions();
  setStatus("Chat renamed");
}

async function deleteCurrentSession() {
  if (!state.sessionId) {
    return;
  }
  await deleteSessionById(state.sessionId);
}

async function copyCurrentTranscript() {
  if (!state.messages.length) {
    return;
  }
  const transcript = serializeConversationToMarkdown();
  await navigator.clipboard.writeText(transcript);
  setStatus("Transcript copied");
}

async function handleSessionListAction(action, sessionId) {
  if (!sessionId) {
    return;
  }
  if (action === "open") {
    await openSession(sessionId);
    return;
  }
  if (action === "archive" || action === "unarchive") {
    toggleSessionArchive(sessionId, action === "archive");
    return;
  }
  if (action === "delete") {
    await deleteSessionById(sessionId);
  }
}

function toggleSessionArchive(sessionId, archived) {
  if (archived) {
    state.archivedSessionIds.add(sessionId);
    if (sessionId === state.sessionId) {
      state.sessionId = "";
      state.messages = [];
      renderMessages();
      updateActiveSessionMeta();
    }
  } else {
    state.archivedSessionIds.delete(sessionId);
  }
  renderSessions();
  queuePersistUIState();
}

async function deleteSessionById(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!window.confirm(`Delete "${session?.title || "this chat"}"?`)) {
    return;
  }
  await api(`/api/sessions/${sessionId}`, { method: "DELETE" });
  state.archivedSessionIds.delete(sessionId);
  if (state.sessionId === sessionId) {
    state.sessionId = "";
    state.messages = [];
  }
  await refreshSessions();
  if (!state.sessionId) {
    const firstVisible = getVisibleSessions()[0];
    if (firstVisible) {
      await openSession(firstVisible.id);
    } else {
      renderMessages();
      updateActiveSessionMeta();
    }
  }
  setStatus("Chat deleted");
}

async function handleMessageAction(action, index) {
  const message = state.messages[index];
  if (!message) {
    return;
  }
  if (action === "resend") {
    dom.questionInput.value = message.content || "";
    await sendMessage();
    return;
  }
  if (action === "retry") {
    await retryLastTurn();
    return;
  }
  if (action === "copy") {
    await navigator.clipboard.writeText(serializeMessageToMarkdown(message, index, { includeHeading: true }));
    setStatus("Message copied");
  }
}

function updateTraceNote() {
  dom.traceVisibilityNote.textContent = state.isSending
    ? "Working..."
    : (state.ui.verbose_trace
      ? "Ready."
      : "Trace hidden.");
}

function updateChatControlSummaries() {
  const selectedProvider = state.providers.find((provider) => provider.id === state.selectedProviderId);
  if (selectedProvider) {
    dom.chatProviderSummary.textContent = `Chat model: ${providerSummaryLabel(selectedProvider)}`;
  } else {
    const intentProvider = providerSummaryLabel(providerFromId(state.modelRouting.intent?.primary_provider_id));
    const synthesisProvider = providerSummaryLabel(providerFromId(state.modelRouting.synthesis?.primary_provider_id));
    dom.chatProviderSummary.textContent =
      `Chat model: ${synthesisProvider}. Intent routing: ${intentProvider}.`;
  }

  dom.chatGatingSummary.textContent =
    "Tools: supported";
}

function updateComposerState() {
  dom.sendButton.disabled = state.isSending;
  dom.retryButton.disabled = state.isSending || !findLastUserQuestion();
  dom.stopButton.disabled = !state.isSending;
  dom.questionInput.disabled = state.isSending;
  dom.providerSelect.disabled = state.isSending;
  dom.renameSessionButton.disabled = !state.sessionId;
  dom.deleteSessionButton.disabled = !state.sessionId || state.isSending;
  dom.copySessionButton.disabled = !state.messages.length;
}

function setView(viewName) {
  if (!VALID_VIEWS.has(viewName)) {
    return;
  }
  Object.entries(dom.views).forEach(([name, view]) => {
    view.classList.toggle("is-active", name === viewName);
  });
  dom.tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });
  syncHashToUIState();
  queuePersistUIState();
}

function setSubtab(subtabName) {
  if (!VALID_SUBTABS.has(subtabName)) {
    return;
  }
  dom.subviews.forEach((view) => {
    view.classList.toggle("is-active", view.id === `subtab-${subtabName}`);
  });
  dom.subtabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.subtab === subtabName);
  });
  syncHashToUIState();
  queuePersistUIState();
}

function renderAppearance() {
  dom.appearanceThemeMode.value = state.appearance.theme_mode || "light";
  dom.appearanceLightTheme.value = state.appearance.light_theme || "quiet_light";
  dom.appearanceDarkTheme.value = state.appearance.dark_theme || "vscode_dark";
}

function applyAppearance() {
  const themeName = resolveThemeName();
  const preset = THEME_PRESETS[themeName] || THEME_PRESETS.quiet_light;
  const root = document.documentElement.style;
  const isDarkTheme = themeName.includes("dark");
  root.setProperty("--bg", preset.bg);
  root.setProperty("--bg-strong", preset.bgStrong);
  root.setProperty("--panel", preset.panel);
  root.setProperty("--panel-strong", preset.panelStrong);
  root.setProperty("--ink", preset.ink);
  root.setProperty("--muted", preset.muted);
  root.setProperty("--line", preset.line);
  root.setProperty("--line-strong", preset.lineStrong);
  root.setProperty("--accent", preset.accent);
  root.setProperty("--accent-deep", preset.accentDeep);
  root.setProperty("--accent-soft", preset.accentSoft);
  root.setProperty("--sage", preset.sage);
  root.setProperty("--user", preset.user);
  root.setProperty("--shadow", preset.shadow || (isDarkTheme ? "0 24px 60px rgba(0, 0, 0, 0.28)" : "0 22px 54px rgba(76, 97, 124, 0.12)"));
  root.setProperty("--glow-top-left", preset.glowTopLeft || "color-mix(in srgb, var(--accent-soft) 56%, white 44%)");
  root.setProperty("--glow-bottom-right", preset.glowBottomRight || "color-mix(in srgb, var(--accent) 18%, transparent 82%)");
  root.setProperty("--appbar-top", preset.appbarTop || (isDarkTheme
    ? "color-mix(in srgb, var(--accent-deep) 34%, var(--bg-strong) 66%)"
    : "color-mix(in srgb, var(--panel) 94%, white 6%)"));
  root.setProperty("--appbar-bottom", preset.appbarBottom || (isDarkTheme
    ? "color-mix(in srgb, var(--bg-strong) 44%, black 56%)"
    : "color-mix(in srgb, var(--panel-strong) 92%, var(--bg) 8%)"));
  root.setProperty("--appbar-ink", preset.appbarInk || (isDarkTheme
    ? "color-mix(in srgb, var(--panel) 84%, white 16%)"
    : "var(--ink)"));
  root.setProperty("--appbar-muted", preset.appbarMuted || (isDarkTheme
    ? "color-mix(in srgb, var(--appbar-ink) 78%, transparent 22%)"
    : "color-mix(in srgb, var(--muted) 88%, transparent 12%)"));
  root.setProperty("--appbar-surface", preset.appbarSurface || (isDarkTheme
    ? "color-mix(in srgb, var(--panel) 10%, transparent 90%)"
    : "color-mix(in srgb, var(--panel) 76%, transparent 24%)"));
  root.setProperty("--appbar-surface-line", preset.appbarSurfaceLine || (isDarkTheme
    ? "color-mix(in srgb, var(--panel) 16%, transparent 84%)"
    : "color-mix(in srgb, var(--line) 92%, white 8%)"));
  root.setProperty("--appbar-active-bg", preset.appbarActiveBg || (isDarkTheme
    ? "color-mix(in srgb, var(--panel) 92%, white 8%)"
    : "color-mix(in srgb, var(--panel) 98%, var(--bg) 2%)"));
  root.setProperty("--appbar-active-shadow", preset.appbarActiveShadow || (isDarkTheme
    ? "0 10px 22px rgba(0, 0, 0, 0.22)"
    : "0 8px 18px rgba(76, 97, 124, 0.10)"));
  root.setProperty("--radius", "22px");
  root.setProperty("--radius-sm", "14px");
  document.documentElement.style.colorScheme = isDarkTheme ? "dark" : "light";
}

async function saveAppearance() {
  const payload = {
    theme_mode: dom.appearanceThemeMode.value,
    light_theme: dom.appearanceLightTheme.value,
    dark_theme: dom.appearanceDarkTheme.value,
  };
  state.appearance = await api("/api/settings/appearance", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  writeStoredAppearance(state.appearance);
  renderAppearance();
  applyAppearance();
  setStatus("Appearance saved");
}

function resolveThemeName() {
  const mode = state.appearance.theme_mode || "light";
  if (mode === "system") {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? state.appearance.dark_theme || "vscode_dark"
      : state.appearance.light_theme || "quiet_light";
  }
  return mode === "dark"
    ? state.appearance.dark_theme || "vscode_dark"
    : state.appearance.light_theme || "quiet_light";
}

function readStoredAppearance() {
  try {
    const raw = window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return {
      theme_mode: String(parsed.theme_mode || "light"),
      light_theme: String(parsed.light_theme || "quiet_light"),
      dark_theme: String(parsed.dark_theme || "vscode_dark"),
    };
  } catch {
    return null;
  }
}

function writeStoredAppearance(appearance) {
  try {
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance));
  } catch {
    // Ignore local storage write failures.
  }
}

function readStoredUIState() {
  try {
    const raw = window.localStorage.getItem(UI_STATE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function queuePersistUIState() {
  window.clearTimeout(uiStatePersistTimer);
  uiStatePersistTimer = window.setTimeout(() => {
    persistUIState();
  }, 120);
}

function persistUIState() {
  try {
    window.localStorage.setItem(UI_STATE_STORAGE_KEY, JSON.stringify(buildUIStateSnapshot()));
  } catch {
    // Ignore local storage write failures.
  }
}

function buildUIStateSnapshot() {
  return {
    view: getActiveViewName(),
    subtab: getActiveSubtabName(),
    sessionId: state.sessionId || "",
    selectedProviderId: state.selectedProviderId || "",
    gatingMode: "bind_all",
    sessionFilter: state.sessionFilter || "active",
    sessionSearch: state.sessionSearch || "",
    archivedSessionIds: Array.from(state.archivedSessionIds),
    sidebarWidth: clampSidebarWidth(state.sidebarWidth),
    workspaceHeight: clampWorkspaceHeight(state.workspaceHeight),
    totalWorkspaceHeight: clampTotalWorkspaceHeight(state.totalWorkspaceHeight),
    providerSort: {
      key: state.providerSort.key || "display_name",
      direction: state.providerSort.direction === "desc" ? "desc" : "asc",
    },
    providerEditor: serializeProviderEditorState(),
    scrollY: Math.max(0, Number(window.scrollY || window.pageYOffset || 0)),
  };
}

function serializeProviderEditorState() {
  const selectedProvider = getCurrentPersistedProvider();
  const rawDraft = dom.providerDisplayName
    ? readProviderEditorForm()
    : (state.providerEditor.draft ? { ...state.providerEditor.draft } : null);
  if (rawDraft) {
    delete rawDraft._pending_secret_value;
  }
  return {
    isNew: Boolean(state.providerEditor.isNew),
    selectedProviderId: selectedProvider?.id || "",
    templateName: dom.providerTemplateSelect?.value || "",
    draft: rawDraft,
  };
}

function resolveStoredProviderSelection(providerId) {
  if (!providerId) {
    return "";
  }
  return state.providers.some((provider) => provider.id === providerId) ? providerId : "";
}

function resolveStoredGatingMode(storedMode, defaultMode) {
  if (VALID_GATING_MODES.has(storedMode)) {
    return storedMode;
  }
  return VALID_GATING_MODES.has(defaultMode) ? defaultMode : "gated";
}

function resolveStoredProviderSort(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return { key: "display_name", direction: "asc" };
  }
  return {
    key: String(snapshot.key || "display_name"),
    direction: snapshot.direction === "desc" ? "desc" : "asc",
  };
}

function restoreProviderEditorState(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    return;
  }
  const selectedIndex = snapshot.selectedProviderId
    ? state.providers.findIndex((provider) => provider.id === snapshot.selectedProviderId)
    : -1;
  const draft = snapshot.draft && typeof snapshot.draft === "object"
    ? { ...makeBlankProvider(), ...snapshot.draft, _pending_secret_value: "" }
    : null;
  if (snapshot.isNew) {
    state.providerEditor = {
      selectedIndex: -1,
      draft: draft || makeBlankProvider(),
      isNew: true,
    };
    return;
  }
  if (selectedIndex >= 0) {
    state.providerEditor = {
      selectedIndex,
      draft: draft ? { ...state.providers[selectedIndex], ...draft } : { ...state.providers[selectedIndex] },
      isNew: false,
    };
  }
}

function resolveInitialSessionId(sessionId) {
  if (!sessionId) {
    return "";
  }
  return state.sessions.some((session) => session.id === sessionId) ? sessionId : "";
}

function applyStoredNavigation(hashUIState, storedUIState) {
  const viewName = VALID_VIEWS.has(hashUIState?.view)
    ? hashUIState.view
    : (VALID_VIEWS.has(storedUIState?.view) ? storedUIState.view : "chat");
  const subtabName = VALID_SUBTABS.has(hashUIState?.subtab)
    ? hashUIState.subtab
    : (VALID_SUBTABS.has(storedUIState?.subtab) ? storedUIState.subtab : "appearance");
  setSubtab(subtabName);
  setView(viewName);
}

function restoreScrollPosition(scrollY) {
  const nextScrollY = Math.max(0, Number(scrollY || 0));
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      window.scrollTo(0, nextScrollY);
    });
  });
}

function initializeWorkspaceResizers() {
  attachPointerResizer(dom.sidebarResizer, "x", (delta) => {
    state.sidebarWidth = clampSidebarWidth(state.sidebarWidth + delta);
    applyWorkspaceLayout();
    queuePersistUIState();
  });
  attachPointerResizer(dom.composerResizer, "y", (delta) => {
    state.workspaceHeight = clampWorkspaceHeight(state.workspaceHeight - delta);
    applyWorkspaceLayout();
    queuePersistUIState();
  });
  attachPointerResizer(dom.workspaceBottomResizer, "y", (delta) => {
    state.totalWorkspaceHeight = clampTotalWorkspaceHeight(state.totalWorkspaceHeight + delta);
    applyWorkspaceLayout();
    queuePersistUIState();
  });
}

function attachPointerResizer(handle, axis, onDelta) {
  if (!handle) {
    return;
  }
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    let previous = axis === "x" ? event.clientX : event.clientY;
    handle.setPointerCapture(event.pointerId);
    const moveTracked = (moveEvent) => {
      const current = axis === "x" ? moveEvent.clientX : moveEvent.clientY;
      onDelta(current - previous);
      previous = current;
    };
    const stop = () => {
      window.removeEventListener("pointermove", moveTracked);
      window.removeEventListener("pointerup", stop);
      handle.classList.remove("is-dragging");
    };
    handle.classList.add("is-dragging");
    window.addEventListener("pointermove", moveTracked);
    window.addEventListener("pointerup", stop, { once: true });
  });
}

function applyWorkspaceLayout() {
  dom.chatWorkspace.style.setProperty("--sessions-pane-width", `${clampSidebarWidth(state.sidebarWidth)}px`);
  dom.chatWorkspace.style.setProperty("--composer-height", `${clampWorkspaceHeight(state.workspaceHeight)}px`);
  dom.chatWorkspace.style.setProperty("--chat-workspace-height", `${clampTotalWorkspaceHeight(state.totalWorkspaceHeight)}px`);
}

function clampSidebarWidth(width) {
  const value = Number(width || 0);
  return Math.max(280, Math.min(560, Number.isFinite(value) ? value : 438));
}

function clampWorkspaceHeight(height) {
  const value = Number(height || 0);
  return Math.max(100, Math.min(560, Number.isFinite(value) ? value : 168));
}

function clampTotalWorkspaceHeight(height) {
  const value = Number(height || 0);
  return Math.max(300, Math.min(1600, Number.isFinite(value) ? value : 600));
}

function getActiveViewName() {
  return dom.tabButtons.find((button) => button.classList.contains("is-active"))?.dataset.view || "chat";
}

function getActiveSubtabName() {
  return dom.subtabButtons.find((button) => button.classList.contains("is-active"))?.dataset.subtab || "appearance";
}

function readHashUIState() {
  const hash = String(window.location.hash || "").replace(/^#/, "").trim();
  if (!hash) {
    return null;
  }
  const [viewPart, subtabPart] = hash.split("/");
  const view = VALID_VIEWS.has(viewPart) ? viewPart : null;
  if (!view) {
    return null;
  }
  return {
    view,
    subtab: VALID_SUBTABS.has(subtabPart) ? subtabPart : null,
  };
}

function syncHashToUIState() {
  const viewName = getActiveViewName();
  const subtabName = getActiveSubtabName();
  const nextHash = viewName === "settings" ? `#settings/${subtabName}` : `#${viewName}`;
  if (window.location.hash === nextHash) {
    return;
  }
  window.history.replaceState(null, "", nextHash);
}

function handleHashNavigation() {
  const hashUIState = readHashUIState();
  if (!hashUIState) {
    return;
  }
  if (hashUIState.subtab) {
    setSubtab(hashUIState.subtab);
  }
  setView(hashUIState.view);
}

async function exportConfigPayload() {
  const response = await api("/api/settings/config");
  const serialized = JSON.stringify(response.config, null, 2);
  const blob = new Blob([`${serialized}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "solar-ai-config.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  setConfigFeedback("Config exported.", false);
  setStatus("Config exported");
}

async function loadCurrentConfigIntoEditor() {
  const response = await api("/api/settings/config");
  dom.configImportText.value = JSON.stringify(response.config, null, 2);
  setConfigFeedback("Loaded current config into the editor.", false);
  setStatus("Config editor populated");
}

async function loadSelectedConfigFile() {
  const [file] = dom.configImportFile.files || [];
  if (!file) {
    return;
  }
  dom.configImportText.value = await file.text();
  setConfigFeedback(`Loaded ${file.name}.`, false);
}

async function importConfigPayload() {
  let parsed;
  try {
    parsed = JSON.parse(dom.configImportText.value);
  } catch (error) {
    throw new Error(`Config JSON is invalid: ${error instanceof Error ? error.message : String(error)}`);
  }
  const response = await api("/api/settings/config", {
    method: "PUT",
    body: JSON.stringify({ config: parsed }),
  });
  state.providers = response.llm_providers || [];
  state.modelRouting = response.model_routing || {};
  state.ui = response.ui || state.ui;
  state.appearance = response.appearance || state.appearance;
  state.gatingMode = "bind_all";
  ensureProviderSelectionAfterRefresh();
  renderProviderControls();
  renderProviderSettings();
  renderUISettings();
  renderAppearance();
  applyAppearance();
  updateTraceNote();
  persistUIState();
  setConfigFeedback("Config imported successfully.", false);
  setStatus("Config imported");
}

function setConfigFeedback(message, isError) {
  dom.configImportFeedback.textContent = message;
  dom.configImportFeedback.classList.toggle("is-error", Boolean(isError));
}

function setStatus(message) {
  dom.statusBanner.textContent = message;
}

function updateActiveSessionMeta() {
  if (!state.sessionId) {
    dom.chatTitle.textContent = "New chat";
    dom.activeSessionMeta.textContent = "No active chat yet.";
    return;
  }
  const session = state.sessions.find((item) => item.id === state.sessionId);
  if (!session) {
    dom.chatTitle.textContent = "Chat";
    dom.activeSessionMeta.textContent = "Active chat loaded.";
    return;
  }
  dom.chatTitle.textContent = session.title || "New chat";
  const updated = formatTime(session.updated_at || session.created_at || "");
  const messageCount = Number(session.message_count || 0);
  dom.activeSessionMeta.textContent =
    `${session.title || "New chat"} • ${messageCount} message${messageCount === 1 ? "" : "s"}` +
    `${updated ? ` • updated ${updated}` : ""}`;
}

function formatSessionSummary(session) {
  const messageCount = Number(session.message_count || 0);
  const updated = formatTime(session.updated_at || session.created_at || "");
  const messageText = `${messageCount} message${messageCount === 1 ? "" : "s"}`;
  return updated ? `${messageText} · ${updated}` : messageText;
}

function buildSessionPreview(session) {
  const title = String(session.title || "New chat").trim();
  if (title === "New chat" && !Number(session.message_count || 0)) {
    return "No messages yet";
  }
  return title.length > 72 ? `${title.slice(0, 72)}...` : title;
}

function getVisibleSessions() {
  const query = state.sessionSearch.trim().toLowerCase();
  return state.sessions.filter((session) => {
    const archived = state.archivedSessionIds.has(session.id);
    if ((state.sessionFilter === "archived") !== archived) {
      return false;
    }
    if (!query) {
      return true;
    }
    return `${session.title || ""} ${formatSessionSummary(session)}`.toLowerCase().includes(query);
  });
}

function findLastUserQuestion() {
  for (let index = state.messages.length - 1; index >= 0; index -= 1) {
    if (state.messages[index].role === "user" && state.messages[index].content) {
      return state.messages[index].content;
    }
  }
  return state.lastQuestion || "";
}

function buildAssistantLabel(message) {
  const commandName = String(message.metadata?.command?.name || message.metadata?.command_name || "").trim();
  if (commandName) {
    return `Command · /${commandName}`;
  }
  const provider = message.metadata?.provider_id || "";
  return provider ? `Assistant · ${provider}` : "Assistant";
}

function handleCommandMenuKeydown(event) {
  if (!isCommandMenuOpen()) {
    return false;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    moveCommandSelection(1);
    return true;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveCommandSelection(-1);
    return true;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    hideCommandMenu();
    return true;
  }
  if (event.key === "Tab") {
    event.preventDefault();
    applyActiveCommandSuggestion();
    return true;
  }
  if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey) {
    const exact = resolveExactCommandMatch(dom.questionInput.value);
    if (!exact) {
      event.preventDefault();
      applyActiveCommandSuggestion();
      return true;
    }
  }
  return false;
}

function syncCommandMenu() {
  const suggestions = getCommandSuggestions(dom.questionInput.value);
  if (!suggestions.length) {
    hideCommandMenu();
    return;
  }
  const previous = state.commandMenu.items[state.commandMenu.activeIndex]?.name || "";
  state.commandMenu.items = suggestions;
  const nextIndex = suggestions.findIndex((item) => item.name === previous);
  state.commandMenu.activeIndex = nextIndex >= 0 ? nextIndex : 0;
  renderCommandMenu();
}

function getCommandSuggestions(value) {
  const trimmed = String(value || "").trimStart();
  if (!trimmed.startsWith("/")) {
    return [];
  }
  const token = trimmed.slice(1).split(/\s/, 1)[0].toLowerCase();
  const hasWhitespaceAfterToken = /\S+\s+/.test(trimmed.slice(1));
  if (hasWhitespaceAfterToken) {
    return [];
  }
  return state.commands
    .filter((command) => !token || command.name.startsWith(token))
    .sort((left, right) => left.name.localeCompare(right.name));
}

function resolveExactCommandMatch(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed.startsWith("/")) {
    return null;
  }
  const token = trimmed.slice(1).split(/\s/, 1)[0].toLowerCase();
  if (!token) {
    return null;
  }
  return state.commands.find((command) => command.name === token) || null;
}

function isCommandMenuOpen() {
  return !dom.commandMenu.hidden && state.commandMenu.items.length > 0;
}

function moveCommandSelection(delta) {
  const size = state.commandMenu.items.length;
  if (!size) {
    return;
  }
  state.commandMenu.activeIndex = (state.commandMenu.activeIndex + delta + size) % size;
  renderCommandMenu();
}

function applyActiveCommandSuggestion() {
  const active = state.commandMenu.items[state.commandMenu.activeIndex];
  if (!active) {
    return;
  }
  dom.questionInput.value = `/${active.name} `;
  hideCommandMenu();
  dom.questionInput.focus();
}

function hideCommandMenu() {
  state.commandMenu.items = [];
  state.commandMenu.activeIndex = 0;
  dom.commandMenu.hidden = true;
  dom.commandMenu.innerHTML = "";
}

function renderCommandMenu() {
  const items = state.commandMenu.items;
  if (!items.length) {
    hideCommandMenu();
    return;
  }
  dom.commandMenu.hidden = false;
  dom.commandMenu.innerHTML = "";
  items.forEach((command, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `command-option${index === state.commandMenu.activeIndex ? " is-active" : ""}`;
    button.innerHTML = `
      <span class="command-option-name">/${escapeHtml(command.name)}</span>
      <span class="command-option-description">${escapeHtml(command.description || "")}</span>
    `;
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      state.commandMenu.activeIndex = index;
      applyActiveCommandSuggestion();
    });
    dom.commandMenu.appendChild(button);
  });
}

function isAssistantMessagePending(message) {
  return message.role === "assistant" && Boolean(message.metadata?.pending);
}

function renderPendingAssistantMessage(message) {
  const statusText = String(message.content || "").trim() || "Thinking now";
  return `
    <div class="ai-thinking" role="status" aria-live="polite" aria-label="Assistant is working">
      <span class="ai-thinking-inline">
        <span class="ai-thinking-core" aria-hidden="true"></span>
        <span class="ai-thinking-rings" aria-hidden="true">
          <span></span><span></span><span></span>
        </span>
      </span>
      <span class="ai-thinking-copy">
        <span class="ai-thinking-text">Thinking now</span>
        <span class="ai-thinking-note">${escapeHtml(statusText)}</span>
      </span>
    </div>
  `;
}

function providerNameFromId(providerId) {
  if (!providerId) {
    return "auto";
  }
  const provider = state.providers.find((item) => item.id === providerId);
  return provider ? provider.display_name || provider.id : providerId;
}

function providerFromId(providerId) {
  if (!providerId) {
    return null;
  }
  return state.providers.find((item) => item.id === providerId) || null;
}

function providerSummaryLabel(provider) {
  if (!provider) {
    return "Auto";
  }
  const providerName = provider.display_name || provider.id || "Provider";
  return provider.model_id ? `${providerName} (${provider.model_id})` : providerName;
}

function defaultProviderOptionLabel() {
  const synthesisProvider = providerFromId(state.modelRouting.synthesis?.primary_provider_id);
  return synthesisProvider
    ? `Auto: ${providerSummaryLabel(synthesisProvider)}`
    : "Auto";
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

function readProviderEditorForm() {
  return {
    id: state.providerEditor.isNew
      ? nextProviderIdSuggestion(PROVIDER_TEMPLATES[dom.providerTemplateSelect.value]?.id_prefix || dom.providerType.value)
      : (getCurrentPersistedProvider()?.id || state.providerEditor.draft?.id || ""),
    display_name: dom.providerDisplayName.value.trim(),
    provider_type: dom.providerType.value,
    model_id: dom.providerModelId.value.trim(),
    auth_mode: dom.providerAuthMode.value,
    secret_ref: dom.providerSecretRef.value.trim(),
    base_url: dom.providerBaseUrl.value.trim(),
    context_window: dom.providerContextWindow.value ? Number(dom.providerContextWindow.value) : null,
    capabilities: splitCapabilities(dom.providerCapabilities.value),
    enabled: dom.providerEnabled.checked,
    _pending_secret_value: dom.providerSecretValue.value.trim(),
    has_secret: getCurrentPersistedProvider()?.has_secret || false,
  };
}

function startProviderDraft(templateName) {
  const draft = templateName ? makeProviderFromTemplate(templateName) : makeBlankProvider();
  state.providerEditor = {
    selectedIndex: -1,
    draft,
    isNew: true,
  };
  renderProviderSettings();
  queuePersistUIState();
}

function selectProvider(index) {
  if (!Number.isInteger(index) || !state.providers[index]) {
    return;
  }
  state.providerEditor = {
    selectedIndex: index,
    draft: { ...state.providers[index] },
    isNew: false,
  };
  queuePersistUIState();
}

function commitProviderDraftFromDom() {
  const draft = readProviderEditorForm();
  validateProviderDraft(draft, { ignoreDuplicateId: !state.providerEditor.isNew });
  if (state.providerEditor.isNew || state.providerEditor.selectedIndex < 0) {
    state.providers.push(draft);
    state.providerEditor = {
      selectedIndex: state.providers.length - 1,
      draft: { ...draft },
      isNew: false,
    };
    return;
  }
  state.providers[state.providerEditor.selectedIndex] = {
    ...state.providers[state.providerEditor.selectedIndex],
    ...draft,
  };
  state.providerEditor.draft = { ...state.providers[state.providerEditor.selectedIndex] };
}

function resetProviderDraft() {
  if (state.providerEditor.isNew) {
    if (state.providers.length > 0) {
      selectProvider(0);
      return;
    }
    state.providerEditor = {
      selectedIndex: -1,
      draft: makeBlankProvider(),
      isNew: true,
    };
    return;
  }
  if (state.providerEditor.selectedIndex >= 0) {
    selectProvider(state.providerEditor.selectedIndex);
  }
  queuePersistUIState();
}

function removeProvider(index) {
  if (!Number.isInteger(index) || !state.providers[index]) {
    return;
  }
  const removed = state.providers[index];
  state.providers.splice(index, 1);
  scrubRoutingForProvider(removed.id);
  if (state.selectedProviderId === removed.id) {
    state.selectedProviderId = "";
  }
  ensureProviderSelectionAfterRefresh(index);
}

function ensureProviderSelectionAfterRefresh(preferredIndex = 0) {
  if (state.providers.length === 0) {
    state.providerEditor = {
      selectedIndex: -1,
      draft: makeBlankProvider(),
      isNew: true,
    };
    return;
  }
  const nextIndex = Math.max(0, Math.min(preferredIndex, state.providers.length - 1));
  selectProvider(nextIndex);
}

function scrubRoutingForProvider(providerId) {
  ["intent", "synthesis"].forEach((purpose) => {
    const rule = state.modelRouting[purpose];
    if (!rule) {
      return;
    }
    if (rule.primary_provider_id === providerId) {
      rule.primary_provider_id = "";
    }
    rule.fallback_provider_ids = (rule.fallback_provider_ids || []).filter((item) => item !== providerId);
  });
}

function getCurrentPersistedProvider() {
  const index = state.providerEditor.selectedIndex;
  return Number.isInteger(index) && index >= 0 ? state.providers[index] || null : null;
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
    context_window: null,
    capabilities: [],
    enabled: true,
    has_secret: false,
    _pending_secret_value: "",
  };
}

function makeProviderFromTemplate(templateName) {
  const template = PROVIDER_TEMPLATES[templateName];
  if (!template) {
    return makeBlankProvider();
  }
  const id = nextProviderIdSuggestion(template.id_prefix);
  return {
    id,
    display_name: template.display_name,
    provider_type: template.provider_type,
    model_id: template.model_id,
    auth_mode: template.auth_mode,
    secret_ref: template.secret_ref,
    base_url: template.base_url,
    context_window: template.context_window || null,
    capabilities: template.capabilities || [],
    enabled: true,
    has_secret: false,
    _pending_secret_value: "",
  };
}

function nextProviderIdSuggestion(prefix) {
  const safePrefix = String(prefix || "provider").trim() || "provider";
  let candidate = safePrefix;
  let counter = 2;
  const existing = new Set(state.providers.map((provider) => provider.id));
  while (existing.has(candidate)) {
    candidate = `${safePrefix}-${counter}`;
    counter += 1;
  }
  return candidate;
}

function providerTypeOptions(selected) {
  return Object.values(PROVIDER_TEMPLATES)
    .map((template) => template.provider_type)
    .filter((value, index, values) => values.indexOf(value) === index)
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

function splitCapabilities(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function updateProviderAuthFields() {
  const authMode = dom.providerAuthMode.value;
  if (authMode === "env_var") {
    dom.providerSecretRefLabel.textContent = "Secret / Env Var";
    dom.providerSecretRef.placeholder = "OPENROUTER_API_KEY";
    dom.providerSecretRef.disabled = false;
    dom.providerSecretValueRow.hidden = true;
    return;
  }
  if (authMode === "stored_secret") {
    dom.providerSecretRefLabel.textContent = "Stored Secret Reference";
    dom.providerSecretRef.placeholder = "provider-secret-ref";
    dom.providerSecretRef.disabled = false;
    dom.providerSecretValueRow.hidden = false;
    return;
  }
  dom.providerSecretRefLabel.textContent = "Secret / Env Var";
  dom.providerSecretRef.placeholder = "";
  dom.providerSecretRef.disabled = true;
  dom.providerSecretRef.value = "";
  dom.providerSecretValueRow.hidden = true;
}

function setProviderFormStatus(message, isError = false) {
  dom.providerFormStatus.textContent = message;
  dom.providerFormStatus.classList.toggle("is-error", Boolean(isError));
}

function validateProviderDraft(provider, { ignoreDuplicateId = false } = {}) {
  if (!provider.display_name) {
    throw new Error("Display Name is required.");
  }
  if (!provider.provider_type) {
    throw new Error("Provider Type is required.");
  }
  if (!provider.model_id) {
    throw new Error("Model ID is required.");
  }
  if (provider.auth_mode !== "none" && !provider.secret_ref) {
    throw new Error("Secret / Env Var is required unless auth mode is none.");
  }
  if (provider.auth_mode === "stored_secret" && !provider.has_secret && !provider._pending_secret_value) {
    throw new Error("API Key Value is required the first time you use stored_secret auth.");
  }
  const duplicates = state.providers.filter((item, index) => {
    if (!item.id || item.id !== provider.id) {
      return false;
    }
    if (ignoreDuplicateId && index === state.providerEditor.selectedIndex) {
      return false;
    }
    return true;
  });
  if (provider.id && duplicates.length > 0) {
    throw new Error(`Duplicate provider id '${provider.id}'.`);
  }
}

function addMissingExampleProviders() {
  const missingKeys = Object.keys(PROVIDER_TEMPLATES).filter((key) => {
    const providerType = PROVIDER_TEMPLATES[key].provider_type;
    return !state.providers.some((provider) => provider.provider_type === providerType);
  });
  if (!missingKeys.length) {
    setProviderFormStatus("All provider example rows already exist.");
    return;
  }
  missingKeys.forEach((key) => {
    const template = PROVIDER_TEMPLATES[key];
    state.providers.push({
      ...makeProviderFromTemplate(key),
      id: nextProviderIdSuggestion(template.id_prefix),
      display_name: `${template.display_name} Example`,
      enabled: false,
    });
  });
  ensureProviderSelectionAfterRefresh(state.providers.length - 1);
  renderProviderSettings();
  setProviderFormStatus(`Added ${missingKeys.length} editable provider example(s). Save Providers to persist.`);
  queuePersistUIState();
}

function providerAuthSummary(provider) {
  if (provider.auth_mode === "stored_secret") {
    return provider.has_secret || provider._pending_secret_value ? "stored secret configured" : "stored secret missing";
  }
  if (provider.auth_mode === "env_var") {
    return provider.secret_ref ? `env: ${provider.secret_ref}` : "env var missing";
  }
  return "no auth";
}

function providerStatus(provider) {
  if (provider.enabled === false) {
    return { key: "disabled", label: "disabled" };
  }
  if (!provider.model_id || (provider.auth_mode !== "none" && !provider.secret_ref)) {
    return { key: "draft", label: "incomplete" };
  }
  if (provider.auth_mode === "stored_secret" && !provider.has_secret && !provider._pending_secret_value) {
    return { key: "warn", label: "missing secret" };
  }
  return { key: "ready", label: "ready" };
}

function renderProviderRegistryRow(provider, index) {
  const capabilities = Array.isArray(provider.capabilities) ? provider.capabilities : [];
  const status = providerStatus(provider);
  const isDefault = state.modelRouting.synthesis?.primary_provider_id === provider.id;
  return `
    <tr class="provider-registry-row${index === state.providerEditor.selectedIndex && !state.providerEditor.isNew ? " is-active" : ""}">
      <td><strong>${escapeHtml(provider.display_name || provider.id)}</strong></td>
      <td><span class="provider-chip">${escapeHtml(provider.provider_type || "provider")}</span></td>
      <td><span class="provider-chip">${escapeHtml(provider.model_id || "no model id")}</span></td>
      <td><span class="provider-chip">${escapeHtml(providerAuthSummary(provider))}</span></td>
      <td><div class="provider-chip-row">${(capabilities.length ? capabilities : ["none"]).map((item) => `<span class="provider-chip">${escapeHtml(item)}</span>`).join("")}</div></td>
      <td><button class="registry-icon-button${provider.enabled !== false ? " is-active" : ""}" type="button" data-action="toggle-enabled" data-index="${index}" title="${provider.enabled !== false ? "Disable" : "Enable"} provider ${escapeAttr(provider.display_name || provider.id || "")}"><span aria-hidden="true">${provider.enabled !== false ? "◉" : "○"}</span></button></td>
      <td><button class="registry-icon-button registry-status-${status.key}" type="button" data-action="check-provider" data-index="${index}" title="Check provider"><span aria-hidden="true">${status.key === "ready" ? "◎" : status.key === "warn" ? "◌" : "◍"}</span></button></td>
      <td>
        <div class="registry-actions">
          <button class="registry-icon-button${isDefault ? " is-active" : ""}" type="button" data-action="set-default" data-index="${index}" title="Set as chat route primary"><span aria-hidden="true">☆</span></button>
          <button class="registry-icon-button" type="button" data-action="edit-provider" data-index="${index}" title="Edit provider"><span aria-hidden="true">✎</span></button>
          <button class="registry-icon-button registry-danger" type="button" data-action="remove-provider" data-index="${index}" title="Delete provider"><span aria-hidden="true">⌫</span></button>
        </div>
      </td>
    </tr>
  `;
}

function renderProviderSortHeader(label, key) {
  const active = state.providerSort.key === key;
  const arrow = active ? (state.providerSort.direction === "asc" ? " ▲" : " ▼") : "";
  return `<th><button class="provider-sort-button${active ? " is-active" : ""}" type="button" data-sort="${escapeAttr(key)}">${escapeHtml(label)}${arrow}</button></th>`;
}

function toggleProviderSort(key) {
  if (state.providerSort.key === key) {
    state.providerSort.direction = state.providerSort.direction === "asc" ? "desc" : "asc";
    return;
  }
  state.providerSort.key = key;
  state.providerSort.direction = "asc";
}

function compareProviderRows(left, right, key) {
  if (key === "enabled") {
    return Number(left.enabled === false) - Number(right.enabled === false);
  }
  if (key === "auth") {
    return providerAuthSummary(left).localeCompare(providerAuthSummary(right));
  }
  if (key === "capabilities") {
    return (left.capabilities || []).join(",").localeCompare((right.capabilities || []).join(","));
  }
  if (key === "status") {
    return providerStatus(left).label.localeCompare(providerStatus(right).label);
  }
  return String(left[key] || "").toLowerCase().localeCompare(String(right[key] || "").toLowerCase());
}

function toggleProviderEnabled(index) {
  if (!Number.isInteger(index) || !state.providers[index]) {
    return;
  }
  state.providers[index].enabled = state.providers[index].enabled === false;
  if (index === state.providerEditor.selectedIndex) {
    state.providerEditor.draft = { ...state.providers[index] };
  }
}

function setChatRouteProvider(index) {
  if (!Number.isInteger(index) || !state.providers[index]) {
    return;
  }
  const providerId = state.providers[index].id;
  state.modelRouting.synthesis = {
    primary_provider_id: providerId,
    fallback_provider_ids: (state.modelRouting.synthesis?.fallback_provider_ids || []).filter((item) => item !== providerId),
  };
}

async function persistPendingProviderSecrets() {
  for (const provider of state.providers) {
    if (provider.auth_mode !== "stored_secret" || !provider.secret_ref || !provider._pending_secret_value) {
      continue;
    }
    await api(`/api/settings/secrets/${encodeURIComponent(provider.secret_ref)}`, {
      method: "PUT",
      body: JSON.stringify({ value: provider._pending_secret_value }),
    });
    provider.has_secret = true;
    provider._pending_secret_value = "";
  }
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

function formatCompactNumber(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "0";
  }
  if (number >= 1000) {
    return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`;
  }
  return String(number);
}

function formatTokenThroughput(outputTokens, elapsedMs) {
  const ms = Number(elapsedMs || 0);
  const tokens = Number(outputTokens || 0);
  if (ms <= 0 || tokens <= 0) {
    return "";
  }
  const rate = tokens / (ms / 1000);
  return rate >= 10 ? String(Math.round(rate)) : rate.toFixed(1);
}

function renderMarkdown(value) {
  const source = String(value || "").replace(/\r\n?/g, "\n");
  if (!source.trim()) {
    return "";
  }

  const fences = [];
  const text = source.replace(/```([^\n`]*)\n?([\s\S]*?)```/g, (_, info, code) => {
    const token = `@@CODEBLOCK${fences.length}@@`;
    fences.push({
      info: String(info || "").trim(),
      code: String(code || "").replace(/\n$/, ""),
    });
    return token;
  });

  return text
    .split(/\n{2,}/)
    .map((block) => renderMarkdownBlock(block.trim(), fences))
    .filter(Boolean)
    .join("");
}

function renderMarkdownBlock(block, fences) {
  if (!block) {
    return "";
  }
  const codeMatch = block.match(/^@@CODEBLOCK(\d+)@@$/);
  if (codeMatch) {
    const fence = fences[Number(codeMatch[1])] || { info: "", code: "" };
    const infoAttr = fence.info ? ` data-language="${escapeAttr(fence.info)}"` : "";
    const label = fence.info ? `<div class="message-code-label">${escapeHtml(fence.info)}</div>` : "";
    return `<div class="message-code-frame"${infoAttr}>${label}<pre class="message-code-block"><code>${escapeHtml(fence.code)}</code></pre></div>`;
  }

  const lines = block.split("\n");
  const heading = block.match(/^(#{1,6})[ \t]+(.+)$/);
  if (heading) {
    const level = Math.min(heading[1].length, 6);
    return `<h${level}>${renderInlineMarkdown(heading[2].trim())}</h${level}>`;
  }

  if (lines.every((line) => /^\s*>/.test(line))) {
    const quoted = lines.map((line) => line.replace(/^\s*> ?/, "")).join("\n");
    return `<blockquote>${renderMarkdown(quoted)}</blockquote>`;
  }

  if (lines.every((line) => /^\s*[-*+]\s+/.test(line))) {
    return `<ul>${lines.map((line) => `<li>${renderInlineMarkdown(line.replace(/^\s*[-*+]\s+/, ""))}</li>`).join("")}</ul>`;
  }

  if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
    return `<ol>${lines.map((line) => `<li>${renderInlineMarkdown(line.replace(/^\s*\d+\.\s+/, ""))}</li>`).join("")}</ol>`;
  }

  return `<p>${lines.map((line) => renderInlineMarkdown(line)).join("<br>")}</p>`;
}

function renderInlineMarkdown(value) {
  const inlineCodes = [];
  const placeholderSource = String(value || "").replace(/`([^`\n]+)`/g, (_, code) => {
    const token = `@@INLINECODE${inlineCodes.length}@@`;
    inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
    return token;
  });

  let html = escapeHtml(placeholderSource);
  html = html.replace(/@@INLINECODE(\d+)@@/g, (_, index) => inlineCodes[Number(index)] || "");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_, label, url) => {
    const safeUrl = sanitizeHref(url);
    if (!safeUrl) {
      return `${label} (${url})`;
    }
    return `<a href="${escapeAttr(safeUrl)}" target="_blank" rel="noreferrer">${label}</a>`;
  });
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  return html;
}

function sanitizeHref(url) {
  const text = String(url || "").trim();
  if (!text) {
    return "";
  }
  try {
    const parsed = new URL(text);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return "";
  }
  return "";
}

function serializeConversationToMarkdown() {
  const session = state.sessions.find((item) => item.id === state.sessionId);
  const title = session?.title || dom.chatTitle?.textContent?.trim() || "New chat";
  const anchorMessage = state.messages.find((message) => message.created_at) || state.messages[0];
  const headingStamp = formatCopyHeadingDate(anchorMessage?.metadata?.telemetry?.finished_at || anchorMessage?.created_at);
  const lines = [`# Chat: ${title}${headingStamp ? ` — ${headingStamp}` : ""}`];

  state.messages.forEach((message, index) => {
    lines.push("", serializeMessageToMarkdown(message, index, { includeHeading: false }));
  });

  return lines.join("\n").trim();
}

function serializeMessageToMarkdown(message, index, options = {}) {
  const includeHeading = Boolean(options.includeHeading);
  const lines = [];
  if (includeHeading) {
    const session = state.sessions.find((item) => item.id === state.sessionId);
    const title = session?.title || dom.chatTitle?.textContent?.trim() || "New chat";
    lines.push(`# Message: ${title}`);
    lines.push("");
  }

  lines.push(buildMessageCopyHeader(message));
  lines.push("");
  lines.push(message.content || "");

  if (message.role === "assistant") {
    const metadata = message.metadata || {};
    if (state.ui.verbose_trace && shouldRenderAgentActivity(metadata) && isAgentActivityOpen(message, index)) {
      lines.push("", serializeAgentActivityToMarkdown(metadata));
    }
    const stats = serializeAssistantStatsToMarkdown(message);
    if (stats) {
      lines.push("", stats);
    }
  }

  return lines.join("\n").trim();
}

function buildMessageCopyHeader(message) {
  const timestamp = formatCopyClock(message.metadata?.telemetry?.finished_at || message.created_at);
  if (message.role !== "assistant") {
    return `## User${timestamp ? ` · ${timestamp}` : ""}`;
  }
  const identity = buildAssistantCopyIdentity(message);
  return `## Assistant${identity ? ` (${identity})` : ""}${timestamp ? ` · ${timestamp}` : ""}`;
}

function buildAssistantCopyIdentity(message) {
  const metadata = message.metadata || {};
  const telemetry = metadata.telemetry || {};
  const parts = [];
  if (metadata.provider_id) {
    parts.push(metadata.provider_id);
  }
  if (telemetry.intent_model) {
    parts.push(telemetry.intent_model);
  }
  if (telemetry.synthesis_model && telemetry.synthesis_model !== telemetry.intent_model) {
    parts.push(telemetry.synthesis_model);
  }
  if (shouldRenderAgentActivity(metadata)) {
    parts.push("Agent");
  }
  return parts.join(" · ");
}

function serializeAgentActivityToMarkdown(metadata) {
  const activity = buildAgentActivityModel(metadata);
  const lines = ["### Agent activity", "", "**Agent run**"];
  const context = buildAgentActivityContext(metadata);
  if (context.length) {
    lines.push("", "#### Context used", "");
    context.forEach((item) => {
      lines.push(`- ${item}`);
    });
  }

  activity.iterations.forEach((iteration) => {
    lines.push("", `#### Iteration ${iteration.number}`, "");
    if (!iteration.tools.length) {
      lines.push("- no tools");
      return;
    }
    iteration.tools.forEach((tool) => {
      lines.push(`- \`${tool.name || "tool"}\`${formatActivityToolMarkdown(tool)}`);
    });
  });

  lines.push("", `**Done · ${activity.stopReason}**`);
  return lines.join("\n");
}

function buildAgentActivityContext(metadata) {
  const items = [];
  if (metadata.gating_mode) {
    items.push(`\`gating_mode\` — ${metadata.gating_mode}`);
  }
  if (Array.isArray(metadata.bound_tools) && metadata.bound_tools.length) {
    items.push(`\`bound_tools\` — ${metadata.bound_tools.map((tool) => `\`${tool}\``).join(", ")}`);
  }
  if (metadata.intent?.summary) {
    items.push(`\`intent\` — ${metadata.intent.summary}`);
  }
  if (metadata.intent?.time_range) {
    items.push(`\`time_range\` — ${metadata.intent.time_range}`);
  }
  return items;
}

function formatActivityToolMarkdown(tool) {
  const parts = [];
  Object.entries(tool.args || {}).forEach(([key, value]) => {
    parts.push(`${key}: ${summarizeActivityValue(value)}`);
  });
  const resultKeys = Object.keys(tool.result || {});
  if (resultKeys.length > 0) {
    parts.push(resultKeys.join(", "));
  }
  if (tool.pending) {
    parts.push("running");
  }
  if (tool.latencyMs > 0) {
    parts.push(`${tool.latencyMs} ms`);
  }
  return parts.length ? ` · ${parts.join(" · ")}` : "";
}

function serializeAssistantStatsToMarkdown(message) {
  const metadata = message.metadata || {};
  const telemetry = metadata.telemetry || {};
  const usage = selectUsageSnapshot(telemetry);
  const elapsedMs = selectElapsedMs(metadata, telemetry);
  const parts = [];
  if (telemetry.intent_model) {
    parts.push(telemetry.intent_model);
  } else if (metadata.provider_id) {
    parts.push(metadata.provider_id);
  }
  if (telemetry.synthesis_model) {
    parts.push(telemetry.synthesis_model);
  }
  if (elapsedMs > 0) {
    parts.push(`${elapsedMs} ms`);
  }
  if (usage.input_tokens > 0 || usage.output_tokens > 0 || usage.total_tokens > 0) {
    parts.push(`↑${formatCompactNumber(usage.input_tokens)}`);
    parts.push(`↓${formatCompactNumber(usage.output_tokens)} tok`);
    const throughput = formatTokenThroughput(usage.output_tokens, elapsedMs);
    if (throughput) {
      parts.push(`${throughput} tok/s`);
    }
  }
  if (Number(metadata.iterations || 0) > 0) {
    parts.push(`${Number(metadata.iterations)} iter`);
  }
  if (!parts.length) {
    return "";
  }
  return `_${parts.join(" · ")}_`;
}

function isAgentActivityOpen(message, index) {
  const key = buildMessageTraceKey(message, index);
  if (Object.prototype.hasOwnProperty.call(state.messageTraceOpen, key)) {
    return Boolean(state.messageTraceOpen[key]);
  }
  return true;
}

function setAgentActivityOpen(message, index, isOpen) {
  state.messageTraceOpen[buildMessageTraceKey(message, index)] = Boolean(isOpen);
}

function buildMessageTraceKey(message, index) {
  return `${message.role}:${message.created_at || "na"}:${index}`;
}

function formatCopyClock(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatCopyHeadingDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
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
