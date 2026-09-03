<template>
  <div class="settings">
    <section class="settings-head panel">
      <button class="btn ghost back-btn" type="button" @click="$emit('back')">← 返回看板</button>
      <div class="settings-title">
        <h2>系统设置</h2>
        <p class="hint">捕获代理、过滤规则与存储限制均可在此配置并即时保存。</p>
      </div>
    </section>

    <div class="settings-grid">
      <article class="panel card">
        <header class="card-head">
          <h3>捕获控制</h3>
          <span class="pill" :data-state="status.status || 'stopped'">
            <i></i>{{ statusLabel }}
          </span>
        </header>
        <dl class="meta-list">
          <div>
            <dt>代理地址</dt>
            <dd>
              <code>{{ status.listen_host || form.listen_host }}:{{ form.listen_port }}</code>
            </dd>
          </div>
          <div>
            <dt>进程 PID</dt>
            <dd>{{ status.pid ?? "—" }}</dd>
          </div>
          <div>
            <dt>CA 证书</dt>
            <dd>{{ status.ca_cert_ready ? "已就绪（可长期复用）" : "未生成（启动捕获后自动创建）" }}</dd>
          </div>
          <div class="path-row">
            <dt>证书路径</dt>
            <dd><code class="path-code">{{ status.ca_cert_path || "—" }}</code></dd>
          </div>
          <div class="path-row">
            <dt>mitm 目录</dt>
            <dd><code class="path-code">{{ status.mitm_confdir || "—" }}</code></dd>
          </div>
        </dl>
        <p class="hint cert-hint">
          证书持久保存在用户目录，不随项目路径变化。在 macOS 钥匙串中信任一次后，后续启动无需重复安装。
        </p>
        <div class="btn-row">
          <button class="btn lime" :disabled="busy || status.status === 'running'" @click="onStart">
            启动捕获
          </button>
          <button class="btn amber" :disabled="busy || status.status !== 'running'" @click="onPause">
            暂停入库
          </button>
          <button class="btn danger" :disabled="busy || status.status === 'stopped'" @click="onStop">
            停止 mitm
          </button>
        </div>
        <a class="link" href="/api/ca-cert">下载 mitm CA 证书</a>
      </article>

      <article class="panel card">
        <header class="card-head">
          <h3>代理监听</h3>
        </header>
        <p class="hint">浏览器 HTTP/HTTPS 代理应指向此地址。修改后若捕获在运行会自动重启 mitm。</p>
        <div class="field-grid">
          <label class="field">
            监听地址 (listen_host)
            <input v-model="form.listen_host" type="text" placeholder="127.0.0.1" />
          </label>
          <label class="field">
            监听端口 (listen_port)
            <input v-model.number="form.listen_port" type="number" min="1" max="65535" />
          </label>
        </div>
        <button class="btn lime" :disabled="busy" type="button" @click="saveListen">保存监听配置</button>
      </article>

      <article class="panel card">
        <header class="card-head">
          <h3>API 服务</h3>
        </header>
        <p class="hint">当前连接 <code>{{ endpoints.local_url || "—" }}</code>。修改 API 端口需重启客户端后生效。</p>
        <div class="field-grid">
          <label class="field">
            绑定地址 (api_host)
            <input v-model="form.api_host" type="text" placeholder="127.0.0.1" />
          </label>
          <label class="field">
            服务端口 (api_port)
            <input v-model.number="form.api_port" type="number" min="1" max="65535" />
          </label>
        </div>
        <button class="btn lime" :disabled="busy" type="button" @click="saveApi">保存 API 配置</button>
      </article>

      <article class="panel card">
        <header class="card-head">
          <h3>存储限制</h3>
        </header>
        <p class="hint">单条 HTTP body 超过此大小将被截断并附加提示。</p>
        <label class="field">
          最大 body 字节数 (max_body_bytes)
          <input v-model.number="form.max_body_bytes" type="number" min="1024" step="1024" />
        </label>
        <p class="hint approx">约 {{ formatBytes(form.max_body_bytes) }}</p>
        <button class="btn lime" :disabled="busy" type="button" @click="saveStorage">保存存储配置</button>
      </article>

      <article class="panel card wide">
        <header class="card-head">
          <h3>静态资源过滤</h3>
          <span class="count">{{ form.static_suffixes.length }} 个后缀</span>
        </header>
        <p class="hint">匹配以下后缀的请求不会入库（如 .js、.png 等）。</p>
        <div class="tags-scroll">
          <div v-if="form.static_suffixes.length" class="tags">
            <span v-for="s in form.static_suffixes" :key="s" class="tag">
              {{ s }}
              <button type="button" aria-label="移除" @click="removeSuffix(s)">×</button>
            </span>
          </div>
          <p v-else class="empty">暂无后缀，所有请求均会尝试入库。</p>
        </div>
        <div class="add-row">
          <input
            v-model="suffixDraft"
            placeholder=".woff2"
            @keydown.enter.prevent="addSuffix"
          />
          <button class="btn ghost" type="button" @click="addSuffix">添加</button>
          <button class="btn ghost" type="button" @click="resetSuffixes">恢复默认</button>
        </div>
        <button class="btn lime" :disabled="busy" type="button" @click="saveSuffixes">保存过滤规则</button>
      </article>

      <article class="panel card wide">
        <header class="card-head">
          <h3>外观</h3>
        </header>
        <p class="hint">主题偏好保存在本地浏览器存储中。</p>
        <div class="theme-row">
          <button
            class="theme-option"
            :class="{ active: theme === 'dark' }"
            type="button"
            @click="setTheme('dark')"
          >
            深色主题
          </button>
          <button
            class="theme-option"
            :class="{ active: theme === 'light' }"
            type="button"
            @click="setTheme('light')"
          >
            浅色主题
          </button>
        </div>
      </article>
    </div>

    <div class="message-slot">
      <p v-if="notice" class="notice">{{ notice }}</p>
      <p v-else-if="localError" class="error">{{ localError }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { api } from "../api";
import { getTheme, applyTheme } from "../theme.js";

const emit = defineEmits(["back", "theme-changed"]);

const DEFAULT_SUFFIXES = [
  ".js", ".mjs", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
  ".ico", ".webp", ".bmp", ".avif", ".woff", ".woff2", ".ttf", ".eot", ".otf",
  ".mp4", ".webm", ".mp3", ".wav", ".ogg", ".pdf", ".zip", ".gz", ".wasm",
];

const busy = ref(false);
const notice = ref("");
const localError = ref("");
const suffixDraft = ref("");
const status = ref({});
const endpoints = ref({});
const theme = ref(getTheme());
let metaTimer = null;

const form = reactive({
  listen_host: "127.0.0.1",
  listen_port: 8080,
  api_host: "127.0.0.1",
  api_port: 18760,
  max_body_bytes: 524288,
  static_suffixes: [],
});

const statusLabel = computed(() => {
  const map = { running: "捕获中", paused: "已暂停", stopped: "未启动" };
  return map[status.value.status] || "未知";
});

function flash(msg, isError = false) {
  notice.value = isError ? "" : msg;
  localError.value = isError ? msg : "";
}

function formatBytes(value) {
  const n = Number(value) || 0;
  if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

function setTheme(value) {
  theme.value = applyTheme(value);
  emit("theme-changed", theme.value);
}

async function refresh() {
  const [st, cfg, health] = await Promise.all([api.status(), api.settings(), api.health()]);
  status.value = st;
  endpoints.value = health;
  form.listen_host = cfg.listen_host;
  form.listen_port = cfg.listen_port;
  form.api_host = cfg.api_host;
  form.api_port = cfg.api_port;
  form.max_body_bytes = cfg.max_body_bytes;
  form.static_suffixes = [...(cfg.static_suffixes || [])];
}

async function savePartial(payload, okMsg) {
  busy.value = true;
  try {
    const res = await api.saveSettings(payload);
    await refresh();
    const msg = res.message || okMsg;
    flash(res.mitm_restarted ? `${msg}（mitm 已重启）` : msg);
  } catch (err) {
    flash(err.message, true);
  } finally {
    busy.value = false;
  }
}

function saveListen() {
  return savePartial(
    { listen_host: form.listen_host, listen_port: form.listen_port },
    "监听配置已保存",
  );
}

function saveApi() {
  return savePartial(
    { api_host: form.api_host, api_port: form.api_port },
    "API 配置已保存，请重启客户端使端口变更生效",
  );
}

function saveStorage() {
  return savePartial({ max_body_bytes: form.max_body_bytes }, "存储配置已保存");
}

function saveSuffixes() {
  return savePartial({ static_suffixes: form.static_suffixes }, "过滤规则已保存");
}

function addSuffix() {
  let value = suffixDraft.value.trim().toLowerCase();
  if (!value) return;
  if (!value.startsWith(".")) value = `.${value}`;
  if (!form.static_suffixes.includes(value)) form.static_suffixes.push(value);
  suffixDraft.value = "";
}

function removeSuffix(value) {
  form.static_suffixes = form.static_suffixes.filter((item) => item !== value);
}

function resetSuffixes() {
  form.static_suffixes = [...DEFAULT_SUFFIXES];
}

async function wrapAction(fn, okMsg) {
  busy.value = true;
  try {
    await fn();
    await refresh();
    if (okMsg) flash(okMsg);
  } catch (err) {
    flash(err.message, true);
  } finally {
    busy.value = false;
  }
}

function onStart() {
  if (status.value.status === "paused") {
    return wrapAction(() => api.resume(), "捕获已恢复");
  }
  return wrapAction(() => api.start(), "捕获已启动");
}

function onPause() {
  return wrapAction(() => api.pause(), "捕获已暂停");
}

function onStop() {
  return wrapAction(() => api.stop(), "mitm 已停止");
}

onMounted(async () => {
  try {
    await refresh();
  } catch (err) {
    flash(err.message, true);
  }
  metaTimer = setInterval(() => refresh().catch(() => {}), 4000);
});

onUnmounted(() => {
  if (metaTimer) clearInterval(metaTimer);
});
</script>

<style scoped>
.settings {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-gutter: stable;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 8px;
}

.settings-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
}

.back-btn {
  flex: 0 0 auto;
}

.settings-title {
  flex: 1;
  min-width: 0;
}

.settings-head h2 {
  font-family: var(--display);
  font-size: var(--font-size-xl);
  color: var(--accent);
  margin: 0 0 6px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.card {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card.wide {
  grid-column: 1 / -1;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.card-head h3 {
  margin: 0;
  font-family: var(--display);
  font-size: var(--font-size-md);
  color: var(--accent);
}

.count {
  color: var(--muted);
  font-size: var(--font-size-xs);
}

.hint,
.empty {
  color: var(--muted);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
  margin: 0;
}

.hint.approx {
  margin-top: -6px;
}

.hint code,
.meta-list code {
  color: var(--accent);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  padding: 0 10px;
  min-height: 26px;
  color: var(--muted);
  font-size: var(--font-size-xs);
}

.pill i {
  width: 7px;
  height: 7px;
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

.meta-list {
  margin: 0;
  display: grid;
  gap: 8px;
}

.meta-list div {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
  font-size: var(--font-size-sm);
}

.meta-list .path-row {
  grid-template-columns: 88px 1fr;
}

.path-code {
  display: block;
  word-break: break-all;
  white-space: pre-wrap;
  line-height: 1.45;
}

.cert-hint {
  margin-top: -4px;
}

.meta-list dt {
  color: var(--muted);
  margin: 0;
}

.meta-list dd {
  margin: 0;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--muted);
  font-size: var(--font-size-sm);
}

.btn-row,
.add-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.link {
  color: var(--link);
  font-size: var(--font-size-sm);
}

.tags-scroll {
  max-height: 180px;
  overflow: auto;
  border: 1px solid var(--line);
  padding: 10px;
  border-radius: 6px;
  background: var(--bg);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--accent);
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: 999px;
}

.tag button {
  min-height: auto;
  border: 0;
  background: none;
  color: var(--muted);
  padding: 0 2px;
  font-size: 14px;
  line-height: 1;
}

.tag button:hover {
  color: var(--danger);
}

.theme-row {
  display: flex;
  gap: 10px;
}

.theme-option {
  flex: 1;
  min-height: var(--control-height);
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--ink);
  border-radius: 6px;
}

.theme-option.active {
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent);
}

.notice {
  color: var(--notice);
  margin: 0;
}

.error {
  color: var(--danger);
  margin: 0;
}

@media (max-width: 900px) {
  .settings-grid,
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
