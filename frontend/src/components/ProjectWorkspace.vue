<template>
  <div class="workspace">
    <section class="project-bar panel">
      <button class="btn ghost" type="button" @click="$emit('back')">← 返回看板</button>
      <div class="project-info">
        <h2>{{ project.name || "加载中..." }}</h2>
        <p class="hint">创建于 {{ project.created_at || "-" }}</p>
        <div class="domains">
          <span v-for="d in project.domains || []" :key="d" class="tag">{{ d }}</span>
        </div>
      </div>
      <div class="project-bar-actions">
        <div class="project-stats">
          <div><b>{{ project.subdomain_count || 0 }}</b><span>子域名</span></div>
          <div><b>{{ project.unique_key_count || 0 }}</b><span>唯一流量</span></div>
          <div><b>{{ project.packet_count || 0 }}</b><span>原始包</span></div>
        </div>
        <div class="project-bar-buttons">
          <button class="btn danger" type="button" :disabled="deleting" @click="confirmDelete">
            删除项目
          </button>
        </div>
      </div>
    </section>

    <div class="layout">
      <aside class="panel side">
        <section>
          <h2>捕获控制</h2>
          <p class="hint">
            代理地址
            <code>{{ status.listen_host || settings.listen_host }}:{{ settings.listen_port }}</code>
          </p>
          <div class="btn-row">
            <button class="btn lime" :disabled="busy || status.status === 'running'" @click="onStart">启动</button>
            <button class="btn amber" :disabled="busy || status.status !== 'running'" @click="onPause">暂停</button>
            <button class="btn danger" :disabled="busy || status.status === 'stopped'" @click="onStop">停止</button>
          </div>
          <a class="ca" href="/api/ca-cert">下载 mitm CA 证书</a>
        </section>

        <section>
          <h2>监听端口</h2>
          <div class="field">
            <label>listen_port</label>
            <input v-model.number="settings.listen_port" type="number" min="1" max="65535" />
          </div>
          <div class="field">
            <label>listen_host</label>
            <input v-model="settings.listen_host" type="text" />
          </div>
          <button class="btn lime full" :disabled="busy" @click="onSaveListen">保存监听配置</button>
        </section>

        <section>
          <h2>静态资源过滤</h2>
          <p class="hint">已配置 {{ settings.static_suffixes.length }} 个后缀。</p>
          <button class="btn ghost full" type="button" @click="suffixOpen = true">配置静态资源后缀</button>
        </section>

        <div class="message-slot">
          <p v-if="notice" class="notice">{{ notice }}</p>
          <p v-else-if="localError" class="error">{{ localError }}</p>
        </div>
      </aside>

      <main class="panel main">
        <nav class="main-tabs">
          <button
            class="main-tab"
            :class="{ active: activeMainTab === 'traffic' }"
            type="button"
            @click="activeMainTab = 'traffic'"
          >
            流量查询
          </button>
          <button
            class="main-tab"
            :class="{ active: activeMainTab === 'recon' }"
            type="button"
            @click="activeMainTab = 'recon'"
          >
            攻击面 Recon
          </button>
        </nav>

        <template v-if="activeMainTab === 'traffic'">
        <section class="query">
          <div class="query-head">
            <h2>项目流量查询</h2>
            <label class="refresh-toggle">
              <input v-model="autoRefresh" type="checkbox" />
              自动刷新
              <select v-model.number="refreshInterval" :disabled="!autoRefresh">
                <option :value="2">2s</option>
                <option :value="3">3s</option>
                <option :value="5">5s</option>
                <option :value="10">10s</option>
              </select>
              <span v-if="autoRefresh" class="pulse-dot"></span>
            </label>
          </div>
          <div class="filters">
            <label class="filter-field filter-host">
              host
              <select v-model="query.host" class="filter-control">
                <option value="">全部（项目范围）</option>
                <option v-for="h in hosts" :key="h" :value="h">{{ h }}</option>
              </select>
            </label>
            <label class="filter-field">
              开始时间 (UTC+8)
              <input v-model="query.start" class="filter-control" type="datetime-local" />
            </label>
            <label class="filter-field">
              结束时间 (UTC+8)
              <input v-model="query.end" class="filter-control" type="datetime-local" />
            </label>
            <label class="filter-field filter-page">
              page
              <input v-model.number="query.page" class="filter-control" type="number" min="1" />
            </label>
            <div class="filter-actions">
              <button class="btn lime" :disabled="queryBusy" @click="searchKeys(true)">查询</button>
              <button class="btn ghost" type="button" @click="resetQuery">重置</button>
            </div>
          </div>
        </section>

        <section class="table-wrap">
          <div class="table-head">
            <span>点击行查看原始报文</span>
            <span v-if="lastRefreshed">最近刷新 {{ lastRefreshed }}</span>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>host</th>
                  <th>接口</th>
                  <th>last_seen</th>
                  <th>count</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!result.items?.length">
                  <td colspan="4" class="empty">该项目暂无流量，请启动捕获并访问项目域名。</td>
                </tr>
                <tr
                  v-for="row in result.items"
                  :key="row.unique_key + '@' + row.host"
                  :class="{ active: selectedKey === row.unique_key && selectedHost === row.host }"
                  @click="openRaw(row)"
                >
                  <td>{{ row.host }}</td>
                  <td class="key">
                    <span class="key-label">{{ row.key_label || row.unique_key }}</span>
                    <span class="key-id" :title="row.unique_key">{{ row.unique_key }}</span>
                  </td>
                  <td>{{ row.last_seen }}</td>
                  <td>{{ row.hit_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <button class="btn ghost" :disabled="!canPrevPage" @click="prevPage">上一页</button>
            <div class="pager-meta">
              <span>第 <b>{{ displayPage }}</b> / <b>{{ totalPages }}</b> 页</span>
              <span class="pager-sep">·</span>
              <span>共 <b>{{ totalItems }}</b> 条</span>
            </div>
            <button class="btn ghost" :disabled="!canNextPage" @click="nextPage">下一页</button>
          </div>
        </section>
        </template>

        <ReconPanel
          v-else
          :project-id="projectId"
          :hosts="hosts"
        />
      </main>
    </div>

    <div v-if="suffixOpen" class="modal-mask" @click.self="suffixOpen = false">
      <div class="modal">
        <div class="modal-top">
          <h3>静态资源后缀</h3>
          <button class="btn ghost" type="button" @click="suffixOpen = false">关闭</button>
        </div>
        <div class="tags-scroll">
          <div class="tags">
            <span v-for="s in suffixDraftList" :key="s" class="tag-edit">
              {{ s }}
              <button type="button" @click="removeSuffix(s)">×</button>
            </span>
          </div>
        </div>
        <div class="add-row">
          <input v-model="suffixDraft" placeholder=".js" @keydown.enter.prevent="addSuffix" />
          <button class="btn ghost" type="button" @click="addSuffix">添加</button>
        </div>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="suffixOpen = false">取消</button>
          <button class="btn lime" :disabled="busy" type="button" @click="saveSuffixModal">保存</button>
        </div>
      </div>
    </div>

    <div v-if="rawOpen" class="drawer-mask" @click.self="closeRaw">
      <aside class="drawer">
        <div class="drawer-top">
          <div>
            <div class="kicker">RAW PACKET</div>
            <h3>{{ selectedLabel }}</h3>
            <p class="hint fingerprint">fingerprint: {{ selectedKey }}</p>
          </div>
          <button class="btn ghost" @click="closeRaw">关闭</button>
        </div>
        <p class="hint">host={{ selectedHost }}</p>
        <article v-for="pkt in visibleRawItems" :key="pkt.id" class="packet">
          <header>
            <span>{{ pkt.captured_at }}</span>
            <span v-if="pkt.hit_count > 1">重复 {{ pkt.hit_count }} 次</span>
            <span>{{ pkt.host }}</span>
          </header>
          <pre>{{ pkt.raw_packet }}</pre>
        </article>
        <div v-if="rawTotal > 1 && !rawExpanded" class="expand-row">
          <button class="btn ghost" type="button" :disabled="rawLoading" @click="expandRaw">
            展开全部报文（共 {{ rawTotal }} 条，已显示 1 条）
          </button>
        </div>
        <div v-else-if="rawLoading" class="expand-row hint">加载中...</div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import ReconPanel from "./ReconPanel.vue";

const props = defineProps({
  projectId: { type: Number, required: true },
});

const emit = defineEmits(["back", "deleted"]);

const deleting = ref(false);
const activeMainTab = ref("traffic");
const busy = ref(false);
const queryBusy = ref(false);
const notice = ref("");
const localError = ref("");
const suffixDraft = ref("");
const suffixOpen = ref(false);
const suffixDraftList = ref([]);
const project = ref({});
const status = ref({});
const hosts = ref([]);
const settings = reactive({
  listen_host: "127.0.0.1",
  listen_port: 8080,
  static_suffixes: [],
});
const query = reactive({ host: "", start: "", end: "", page: 1 });
const result = ref({ items: [], total: 0, page: 1, page_size: 20 });
const raw = ref({ items: [], total: 0 });
const rawOpen = ref(false);
const rawExpanded = ref(false);
const rawLoading = ref(false);
const rawTotal = ref(0);
const selectedKey = ref("");
const selectedLabel = ref("");
const selectedHost = ref("");
const autoRefresh = ref(true);
const refreshInterval = ref(3);
const lastRefreshed = ref("");
let metaTimer = null;
let queryTimer = null;
let hostWatchPaused = false;

const totalItems = computed(() => result.value.total || 0);
const pageSize = computed(() => result.value.page_size || 20);
const currentPage = computed(() => result.value.page || query.page || 1);
const totalPages = computed(() => {
  if (totalItems.value === 0) return 0;
  return Math.ceil(totalItems.value / pageSize.value);
});
const canPrevPage = computed(() => currentPage.value > 1);
const canNextPage = computed(() => totalPages.value > 0 && currentPage.value < totalPages.value);
const displayPage = computed(() => (totalPages.value === 0 ? 0 : currentPage.value));
const visibleRawItems = computed(() => {
  if (!rawExpanded.value && raw.value.items?.length) {
    return [raw.value.items[0]];
  }
  return raw.value.items || [];
});

function flash(msg, isError = false) {
  notice.value = isError ? "" : msg;
  localError.value = isError ? msg : "";
}

function formatNow() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

async function loadProject() {
  project.value = await api.project(props.projectId);
}

async function refreshMeta() {
  const [st, hs, cfg] = await Promise.all([
    api.status(),
    api.hosts({ project_id: props.projectId }),
    api.settings(),
  ]);
  status.value = st;
  hosts.value = hs.items || [];
  settings.listen_host = cfg.listen_host;
  settings.listen_port = cfg.listen_port;
  settings.static_suffixes = [...(cfg.static_suffixes || [])];
  await loadProject();
}

async function searchKeys(showNotice = false) {
  queryBusy.value = true;
  try {
    result.value = await api.packets({
      project_id: props.projectId,
      host: query.host,
      start: query.start,
      end: query.end,
      page: query.page,
    });
    lastRefreshed.value = formatNow();
    if (showNotice) flash(`返回 ${result.value.total} 个唯一键`);
  } catch (err) {
    if (showNotice) flash(err.message, true);
  } finally {
    queryBusy.value = false;
  }
}

async function openRaw(row) {
  selectedKey.value = row.unique_key;
  selectedLabel.value = row.key_label || row.unique_key;
  selectedHost.value = row.host;
  rawOpen.value = true;
  rawExpanded.value = false;
  rawLoading.value = true;
  try {
    raw.value = await api.packets({
      project_id: props.projectId,
      host: row.host,
      start: query.start,
      end: query.end,
      unique_key: row.unique_key,
      page: 1,
      page_size: 1,
    });
    rawTotal.value = raw.value.total || raw.value.items?.length || 0;
  } finally {
    rawLoading.value = false;
  }
}

async function expandRaw() {
  rawLoading.value = true;
  try {
    raw.value = await api.packets({
      project_id: props.projectId,
      host: selectedHost.value,
      start: query.start,
      end: query.end,
      unique_key: selectedKey.value,
      page: 1,
      page_size: Math.min(rawTotal.value, 100),
    });
    rawExpanded.value = true;
  } catch (err) {
    flash(err.message, true);
  } finally {
    rawLoading.value = false;
  }
}

function closeRaw() {
  rawOpen.value = false;
  rawExpanded.value = false;
  raw.value = { items: [], total: 0 };
  rawTotal.value = 0;
}

function resetQuery() {
  hostWatchPaused = true;
  query.host = "";
  query.start = "";
  query.end = "";
  query.page = 1;
  setupQueryTimer();
  hostWatchPaused = false;
  searchKeys(true);
}

function prevPage() {
  query.page = Math.max(1, query.page - 1);
  searchKeys(true);
}

function nextPage() {
  query.page += 1;
  searchKeys(true);
}

function addSuffix() {
  let value = suffixDraft.value.trim().toLowerCase();
  if (!value) return;
  if (!value.startsWith(".")) value = `.${value}`;
  if (!suffixDraftList.value.includes(value)) suffixDraftList.value.push(value);
  suffixDraft.value = "";
}

function removeSuffix(value) {
  suffixDraftList.value = suffixDraftList.value.filter((item) => item !== value);
}

async function saveSuffixModal() {
  busy.value = true;
  try {
    await api.saveSettings({
      listen_host: settings.listen_host,
      listen_port: settings.listen_port,
      static_suffixes: suffixDraftList.value,
    });
    await refreshMeta();
    suffixOpen.value = false;
    flash("静态资源后缀已保存");
  } catch (err) {
    flash(err.message, true);
  } finally {
    busy.value = false;
  }
}

async function wrap(fn, okMsg) {
  busy.value = true;
  try {
    await fn();
    await refreshMeta();
    if (okMsg) flash(okMsg);
  } catch (err) {
    flash(err.message, true);
  } finally {
    busy.value = false;
  }
}

function onStart() {
  if (status.value.status === "paused") return wrap(() => api.resume(), "捕获已恢复");
  return wrap(() => api.start(), "捕获已启动");
}

function onPause() {
  return wrap(() => api.pause(), "捕获已暂停");
}

function onStop() {
  return wrap(() => api.stop(), "mitm 已停止");
}

async function onSaveListen() {
  busy.value = true;
  try {
    const res = await api.saveSettings({
      listen_host: settings.listen_host,
      listen_port: settings.listen_port,
      static_suffixes: settings.static_suffixes,
    });
    await refreshMeta();
    flash(
      res.mitm_restarted
        ? `监听已切换为 ${res.settings.listen_host}:${res.settings.listen_port}，mitm 已自动重启`
        : "监听配置已保存；捕获进程未运行，下次启动时生效",
    );
  } catch (err) {
    flash(err.message, true);
  } finally {
    busy.value = false;
  }
}

async function confirmDelete() {
  const name = project.value.name || "该项目";
  const ok = window.confirm(
    `确定删除项目「${name}」？\n\n仅删除项目配置，已捕获的流量数据会保留在数据库中。`,
  );
  if (!ok) return;
  deleting.value = true;
  try {
    await api.deleteProject(props.projectId);
    emit("deleted", name);
  } catch (err) {
    flash(err.message, true);
  } finally {
    deleting.value = false;
  }
}

function setupQueryTimer() {
  if (queryTimer) clearInterval(queryTimer);
  queryTimer = null;
  if (!autoRefresh.value || activeMainTab.value !== "traffic") return;
  queryTimer = setInterval(() => {
    if (!queryBusy.value) searchKeys(false);
  }, refreshInterval.value * 1000);
}

watch(activeMainTab, setupQueryTimer);

function onHostChange() {
  query.page = 1;
  setupQueryTimer();
  searchKeys(false);
}

watch(
  () => query.host,
  (host, prev) => {
    if (hostWatchPaused || host === prev) return;
    onHostChange();
  },
);

watch([autoRefresh, refreshInterval], setupQueryTimer);

watch(
  () => props.projectId,
  async () => {
    resetQuery();
    await refreshMeta();
    await searchKeys(false);
  },
);

onMounted(async () => {
  try {
    await refreshMeta();
    await searchKeys(false);
  } catch (err) {
    flash(err.message, true);
  }
  metaTimer = setInterval(() => refreshMeta().catch(() => {}), 4000);
  setupQueryTimer();
});

onUnmounted(() => {
  if (metaTimer) clearInterval(metaTimer);
  if (queryTimer) clearInterval(queryTimer);
});

watch(
  () => suffixOpen.value,
  (open) => {
    if (open) suffixDraftList.value = [...settings.static_suffixes];
  },
);
</script>

<style scoped>
.workspace {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 8px;
}

.project-bar {
  margin: 14px 24px 0;
  padding: 14px 16px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
}

.project-bar-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.project-info h2 {
  margin: 0 0 4px;
  font-family: var(--display);
  color: var(--ink);
  font-size: var(--font-size-xl);
}

.domains {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tag {
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--accent);
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: 999px;
}

.project-bar-buttons {
  display: flex;
  gap: 8px;
}

.project-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(70px, 1fr));
  gap: 10px;
}

.project-stats div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: right;
}

.project-stats b {
  color: var(--accent);
  font-size: 20px;
}

.project-stats span,
.hint,
.empty {
  color: var(--muted);
  font-size: var(--font-size-sm);
}

.main {
  padding: 14px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.main-tab {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  padding: 7px 14px;
  font-size: var(--font-size-sm);
  font-family: var(--display);
  border-radius: 6px;
  cursor: pointer;
}

.main-tab.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--btn-ghost-hover-bg);
}

.layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 14px;
  padding: 14px 24px 16px;
}

.side section + section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
}

.side {
  padding: 14px;
  min-height: 0;
  overflow: auto;
}

.side h2,
.query-head h2 {
  font-family: var(--display);
  font-size: 14px;
  color: var(--accent);
  margin: 0 0 10px;
}

code {
  color: var(--accent);
}

.btn-row,
.add-row,
.pager,
.filters,
.modal-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  padding: 7px 11px;
  font-size: 12px;
  border-radius: 6px;
  cursor: pointer;
}

.btn.lime {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--btn-primary-fg);
}

.btn.amber {
  border-color: var(--warning);
  color: var(--warning);
}

.btn.ghost:hover,
.btn.amber:hover {
  background: var(--btn-ghost-hover-bg);
}

.btn.full {
  width: 100%;
  margin-top: 8px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 12px;
}

input,
select,
textarea {
  background: var(--input-bg);
  border: 1px solid var(--line);
  color: var(--ink);
  padding: 7px 9px;
  border-radius: 6px;
  font-size: 12px;
}

.ca {
  display: inline-block;
  margin-top: 10px;
  color: var(--link);
  font-size: 12px;
}

.notice {
  color: var(--notice);
}

.error {
  color: var(--danger);
}

.query-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.refresh-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--muted);
  font-size: var(--font-size-sm);
  margin: 0;
}

.filter-host {
  min-width: 180px;
  flex: 1 1 180px;
  max-width: 280px;
}

.filter-field:not(.filter-host):not(.filter-page) {
  flex: 0 0 196px;
}

.filter-page {
  flex: 0 0 88px;
}

.filters .filter-control {
  box-sizing: border-box;
  width: 100%;
  height: var(--control-height);
  min-height: var(--control-height);
  margin: 0;
  padding: 0 9px;
  line-height: 1.2;
  font-size: var(--font-size-sm);
}

.filters input[type="datetime-local"].filter-control {
  padding: 0 8px;
}

.filter-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: var(--control-height);
}

.filter-actions .btn {
  min-height: var(--control-height);
  height: var(--control-height);
  padding: 0 11px;
}

.table-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin-top: 12px;
}

.table-head {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  margin-bottom: 6px;
  font-size: var(--font-size-sm);
}

.pager {
  display: grid;
  grid-template-columns: 96px 1fr 96px;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  min-height: var(--control-height);
}

.pager-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--muted);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.pager-meta b {
  color: var(--accent);
  font-weight: 600;
}

.pager-sep {
  color: var(--line);
}

.pager .btn {
  width: 100%;
}

.table-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--bg);
  scrollbar-gutter: stable;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--line);
}

thead th {
  position: sticky;
  top: 0;
  background: var(--table-head-bg);
}

td.key {
  color: var(--accent);
}

.key-label {
  display: block;
  word-break: break-all;
}

.key-id {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: var(--font-size-xs);
  word-break: break-all;
}

.fingerprint {
  margin-top: 6px;
  word-break: break-all;
}

.expand-row {
  margin-top: 12px;
  text-align: center;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.active {
  background: var(--row-hover);
}

.modal-mask,
.drawer-mask {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-mask {
  justify-content: flex-end;
}

.modal,
.drawer {
  background: var(--modal-bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}

.modal {
  width: min(520px, calc(100vw - 32px));
}

.drawer {
  width: min(760px, 100%);
  height: 100%;
  border-radius: 0;
  overflow: auto;
}

.tags-scroll {
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--line);
  padding: 10px;
  border-radius: 6px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-edit {
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

.tag-edit button {
  min-height: auto;
  border: 0;
  background: none;
  color: var(--muted);
  padding: 0 2px;
  font-size: 14px;
  line-height: 1;
}

.modal-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.modal-top h3 {
  margin: 0;
  color: var(--accent);
  font-family: var(--display);
}

.kicker {
  color: var(--accent-dim);
  letter-spacing: 0.18em;
  font-size: var(--font-size-xs);
}

.drawer-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.drawer-top h3 {
  margin: 0;
  color: var(--accent);
  font-family: var(--display);
  word-break: break-all;
}

.packet {
  border: 1px solid var(--line);
  margin-top: 12px;
  border-radius: 6px;
  overflow: hidden;
}

.packet header {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  color: var(--muted);
  background: var(--bg-2);
}

pre {
  margin: 0;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--pre-fg);
  background: var(--bg-2);
  max-height: 420px;
  overflow: auto;
}

@media (max-width: 980px) {
  .project-bar,
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
