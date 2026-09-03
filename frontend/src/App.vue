<template>
  <div class="shell">
    <header class="topbar">
      <button class="brand" type="button" @click="goDashboard">
        <img class="brand-logo" src="/logo.png" alt="WIRETAPPP" width="44" height="44" />
        <div>
          <div class="kicker">LOCAL BROWSER INTERCEPT</div>
          <h1>WIRETAPPP <span>被动流量捕获</span></h1>
        </div>
      </button>
      <div class="top-meta">
        <button
          v-if="view === 'dashboard'"
          class="nav-btn"
          type="button"
          @click="goSettings"
        >
          设置
        </button>
        <button
          class="theme-toggle"
          type="button"
          :title="theme === 'dark' ? '切换为浅色主题' : '切换为深色主题'"
          @click="onToggleTheme"
        >
          <span class="theme-icon" aria-hidden="true">{{ theme === "dark" ? "☀" : "☾" }}</span>
          <span class="theme-label">{{ theme === "dark" ? "浅色主题" : "深色主题" }}</span>
        </button>
        <div class="pill" :data-state="status.status || 'stopped'">
          <i></i>{{ statusLabel }}
        </div>
        <div class="stat">
          PKT <b>{{ stats.packet_count || 0 }}</b>
        </div>
        <div class="stat">
          KEY <b>{{ stats.unique_key_count || 0 }}</b>
        </div>
        <div class="stat">
          HOST <b>{{ stats.host_count || 0 }}</b>
        </div>
        <div v-if="endpoints.local_url" class="api-endpoints" :title="apiTooltip">
          <span class="api-label">API</span>
          <span class="api-url">{{ endpoints.local_url }}</span>
        </div>
      </div>
    </header>

    <ProjectDashboard
      v-if="view === 'dashboard'"
      ref="dashboardRef"
      @open="openProject"
      @open-settings="goSettings"
      @notice="flash"
      @error="flash($event, true)"
    />
    <SettingsPage
      v-else-if="view === 'settings'"
      @back="goDashboard"
      @theme-changed="theme = $event"
    />
    <ProjectWorkspace
      v-else
      :project-id="activeProjectId"
      @back="goDashboard"
      @deleted="onProjectDeleted"
    />

    <div class="toast-host" aria-live="polite">
      <p v-if="notice && view !== 'project'" class="toast notice">{{ notice }}</p>
      <p v-else-if="error && view !== 'project'" class="toast error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { api } from "./api";
import ProjectDashboard from "./components/ProjectDashboard.vue";
import ProjectWorkspace from "./components/ProjectWorkspace.vue";
import SettingsPage from "./components/SettingsPage.vue";
import { getTheme, toggleTheme } from "./theme.js";

const view = ref("dashboard");
const activeProjectId = ref(null);
const dashboardRef = ref(null);
const status = ref({});
const stats = ref({});
const endpoints = ref({});
const notice = ref("");
const error = ref("");
const theme = ref(getTheme());
let metaTimer = null;

const statusLabel = computed(() => {
  const map = { running: "RUNNING 捕获中", paused: "PAUSED 已暂停", stopped: "STOPPED 未启动" };
  return map[status.value.status] || "UNKNOWN";
});

const apiTooltip = computed(() => {
  const lines = [`本机: ${endpoints.value.local_url || "-"}`];
  (endpoints.value.lan_urls || []).forEach((url) => lines.push(`局域网: ${url}`));
  lines.push("同网段机器可直接调用 /api/*，无需鉴权");
  return lines.join("\n");
});

function flash(msg, isError = false) {
  notice.value = isError ? "" : msg;
  error.value = isError ? msg : "";
}

async function refreshMeta() {
  const [st, ss, health] = await Promise.all([api.status(), api.stats(), api.health()]);
  status.value = st;
  stats.value = ss;
  endpoints.value = health;
}

function openProject(projectId) {
  activeProjectId.value = projectId;
  view.value = "project";
  notice.value = "";
  error.value = "";
}

function goDashboard() {
  view.value = "dashboard";
  activeProjectId.value = null;
  dashboardRef.value?.loadDashboard?.();
}

function goSettings() {
  view.value = "settings";
  activeProjectId.value = null;
  notice.value = "";
  error.value = "";
}

function onProjectDeleted(name) {
  goDashboard();
  flash(`项目「${name}」已删除`);
}

function onToggleTheme() {
  theme.value = toggleTheme();
}

onMounted(async () => {
  try {
    await refreshMeta();
  } catch (err) {
    flash(err.message, true);
  }
  metaTimer = setInterval(() => refreshMeta().catch(() => {}), 4000);
});

onUnmounted(() => {
  if (metaTimer) clearInterval(metaTimer);
});
</script>

<style scoped>
.shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.topbar {
  flex: 0 0 auto;
  min-height: var(--topbar-height);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 14px 24px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}

.brand {
  display: flex;
  gap: 14px;
  align-items: center;
  background: none;
  border: 0;
  padding: 0;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.brand-logo {
  width: 44px;
  height: 44px;
  border-radius: 23%;
  flex: 0 0 auto;
  box-shadow: 0 0 18px var(--radar-glow);
}

.radar {
  width: 44px;
  height: 44px;
  border: 1px solid var(--accent);
  border-radius: 50%;
  position: relative;
  box-shadow: 0 0 18px var(--radar-glow);
}

.radar::before,
.radar::after {
  content: "";
  position: absolute;
  inset: 8px;
  border: 1px solid var(--radar-ring);
  border-radius: 50%;
}

.radar::after {
  inset: 14px;
  background: conic-gradient(from 0deg, transparent 70%, var(--accent));
  animation: sweep 3.6s linear infinite;
}

@keyframes sweep {
  to {
    transform: rotate(360deg);
  }
}

.kicker {
  color: var(--accent-dim);
  letter-spacing: 0.22em;
  font-size: var(--font-size-xs);
}

h1 {
  font-family: var(--display);
  font-weight: 600;
  margin: 0;
  font-size: var(--font-size-display);
  letter-spacing: 0.08em;
}

h1 span {
  color: var(--muted);
  font-size: var(--font-size-md);
  margin-left: 10px;
}

.theme-toggle,
.nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--ink);
  padding: 0 10px;
  font-size: var(--font-size-sm);
  border-radius: 6px;
  min-height: var(--control-height);
}

.nav-btn.active {
  border-color: var(--accent);
  color: var(--accent);
}

.theme-toggle {
  min-width: 108px;
}

.theme-label {
  display: inline-block;
  min-width: 4em;
  text-align: left;
}

.theme-toggle:hover {
  background: var(--btn-ghost-hover-bg);
  border-color: var(--accent);
}

.top-meta {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}

.pill {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  padding: 0 10px;
  min-height: var(--control-height);
  color: var(--muted);
  font-size: var(--font-size-sm);
}

.pill i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
}

.pill[data-state="running"] {
  color: var(--accent);
  border-color: var(--accent);
}

.pill[data-state="running"] i {
  background: var(--accent);
}

.pill[data-state="paused"] {
  color: var(--warning);
  border-color: var(--warning);
}

.pill[data-state="paused"] i {
  background: var(--warning);
}

.pill[data-state="stopped"] i {
  background: var(--danger);
}

.stat {
  font-size: var(--font-size-sm);
}

.stat b {
  color: var(--accent);
  margin-left: 6px;
}

.api-endpoints {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  padding: 0 10px;
  min-height: var(--control-height);
  font-size: var(--font-size-xs);
  color: var(--muted);
  max-width: min(420px, 40vw);
}

.api-label {
  color: var(--accent-dim);
  flex: 0 0 auto;
}

.api-url {
  color: var(--accent);
  word-break: break-all;
  line-height: 1.3;
  padding: 4px 0;
}
</style>
