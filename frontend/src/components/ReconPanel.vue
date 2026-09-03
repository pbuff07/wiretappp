<template>
  <div class="recon">
    <div class="recon-head">
      <nav class="recon-nav">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="recon-tab"
          :class="{ active: view === tab.id }"
          type="button"
          @click="switchView(tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>
      <label class="refresh-toggle">
        <input v-model="autoRefresh" type="checkbox" />
        自动刷新
        <select v-model.number="refreshInterval" :disabled="!autoRefresh">
          <option :value="3">3s</option>
          <option :value="5">5s</option>
          <option :value="10">10s</option>
        </select>
        <span v-if="autoRefresh" class="pulse-dot"></span>
      </label>
    </div>

    <p v-if="loadError" class="recon-error">{{ loadError }}</p>

    <!-- 概览 -->
    <section v-if="view === 'overview'" class="recon-body">
      <div v-if="overviewLoading && !overview" class="empty-state">加载攻击面概览...</div>
      <div v-else-if="!overview && loadError" class="empty-state">{{ loadError }}</div>
      <template v-else-if="overview">
        <div class="summary-grid">
          <div class="summary-card">
            <b>{{ overview.sitemap_summary?.host_count || 0 }}</b>
            <span>Host</span>
          </div>
          <div class="summary-card">
            <b>{{ overview.sitemap_summary?.endpoint_count || 0 }}</b>
            <span>端点</span>
          </div>
          <div class="summary-card">
            <b>{{ overview.hosts?.length || 0 }}</b>
            <span>项目 Host</span>
          </div>
          <div class="summary-card">
            <b>{{ newCount }}</b>
            <span>新端点</span>
          </div>
        </div>

        <div class="overview-since">
          <label class="filter-field">
            新端点起始 (UTC+8)
            <input v-model="sinceInput" class="filter-control" type="datetime-local" />
          </label>
          <button class="btn ghost" type="button" @click="applySince">应用</button>
          <button v-if="sinceInput" class="btn ghost" type="button" @click="clearSince">清除</button>
        </div>

        <div v-if="overview.hosts?.length" class="host-tags">
          <span v-for="h in overview.hosts" :key="h" class="tag">{{ h }}</span>
        </div>

        <div class="section-block">
          <div class="section-title">
            <h3>Top 端点</h3>
            <span v-if="lastRefreshed">最近刷新 {{ lastRefreshed }}</span>
          </div>
          <div class="table-scroll compact">
            <table>
              <thead>
                <tr>
                  <th>method</th>
                  <th>path</th>
                  <th>host</th>
                  <th>hits</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!overview.top_endpoints?.length">
                  <td colspan="4" class="empty">暂无端点，请启动捕获并访问项目域名。</td>
                </tr>
                <tr
                  v-for="row in overview.top_endpoints"
                  :key="row.fingerprint + '@' + row.host"
                  @click="openDetail(row)"
                >
                  <td><span class="method" :data-method="row.method">{{ row.method }}</span></td>
                  <td class="path">{{ row.path }}</td>
                  <td>{{ row.host }}</td>
                  <td>{{ row.hit_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="overview.new_endpoints?.length" class="section-block">
          <div class="section-title">
            <h3>新发现端点</h3>
            <span class="hint">since {{ overview.new_endpoints_since }}</span>
          </div>
          <div class="table-scroll compact">
            <table>
              <thead>
                <tr>
                  <th>method</th>
                  <th>path</th>
                  <th>host</th>
                  <th>first_seen</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in overview.new_endpoints"
                  :key="'new-' + row.fingerprint + '@' + row.host"
                  @click="openDetail(row)"
                >
                  <td><span class="method" :data-method="row.method">{{ row.method }}</span></td>
                  <td class="path">{{ row.path }}</td>
                  <td>{{ row.host }}</td>
                  <td>{{ row.first_seen }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </section>

    <!-- 端点目录 -->
    <section v-else-if="view === 'endpoints'" class="recon-body">
      <div class="filters">
        <label class="filter-field filter-host">
          host
          <select v-model="query.host" class="filter-control">
            <option value="">全部</option>
            <option v-for="h in hosts" :key="h" :value="h">{{ h }}</option>
          </select>
        </label>
        <label class="filter-field">
          method
          <select v-model="query.method" class="filter-control">
            <option value="">全部</option>
            <option v-for="m in methods" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <label class="filter-field">
          path 包含
          <input v-model="query.path_contains" class="filter-control" type="text" placeholder="/api/" />
        </label>
        <label class="filter-field">
          搜索 q
          <input v-model="query.q" class="filter-control" type="text" placeholder="path / host / label" />
        </label>
        <label class="filter-field">
          since (UTC+8)
          <input v-model="query.since" class="filter-control" type="datetime-local" />
        </label>
        <label class="filter-field">
          sort
          <select v-model="query.sort" class="filter-control">
            <option value="last_seen">last_seen</option>
            <option value="first_seen">first_seen</option>
            <option value="hit_count">hit_count</option>
          </select>
        </label>
        <label class="filter-field filter-page">
          page
          <input v-model.number="query.page" class="filter-control" type="number" min="1" />
        </label>
        <div class="filter-actions">
          <button class="btn lime" :disabled="listBusy" @click="searchEndpoints(true)">查询</button>
          <button class="btn ghost" type="button" @click="resetEndpointQuery">重置</button>
        </div>
      </div>

      <div class="table-wrap">
        <div class="table-head">
          <span>点击行查看端点详情（脱敏样本）</span>
          <span v-if="lastRefreshed">最近刷新 {{ lastRefreshed }}</span>
        </div>
        <div v-if="listBusy && !listResult.items?.length" class="empty-state">加载端点目录...</div>
        <div v-else-if="loadError && !listResult.items?.length" class="empty-state">{{ loadError }}</div>
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>method</th>
                <th>path</th>
                <th>host</th>
                <th>params</th>
                <th>first_seen</th>
                <th>last_seen</th>
                <th>hits</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!listResult.items?.length">
                <td colspan="7" class="empty">暂无匹配端点。</td>
              </tr>
              <tr
                v-for="row in listResult.items"
                :key="row.fingerprint + '@' + row.host"
                :class="{ active: selectedFingerprint === row.fingerprint && selectedHost === row.host }"
                @click="openDetail(row)"
              >
                <td><span class="method" :data-method="row.method">{{ row.method }}</span></td>
                <td class="path">{{ row.path }}</td>
                <td>{{ row.host }}</td>
                <td class="params">
                  <span v-if="row.url_param_names?.length" class="param-tag" title="URL 参数">
                    url:{{ row.url_param_names.join(",") }}
                  </span>
                  <span v-if="row.body_param_names?.length" class="param-tag body" title="Body 参数">
                    body:{{ row.body_param_names.join(",") }}
                  </span>
                  <span v-if="!row.url_param_names?.length && !row.body_param_names?.length" class="hint">—</span>
                </td>
                <td>{{ row.first_seen }}</td>
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
      </div>
    </section>

    <!-- 站点地图 -->
    <section v-else class="recon-body">
      <div class="filters">
        <label class="filter-field filter-host">
          host
          <select v-model="sitemapHost" class="filter-control">
            <option value="">全部 Host</option>
            <option v-for="h in hosts" :key="h" :value="h">{{ h }}</option>
          </select>
        </label>
        <div class="filter-actions">
          <button class="btn lime" :disabled="sitemapBusy" @click="loadSitemap(true)">刷新地图</button>
        </div>
      </div>

      <div v-if="sitemapBusy && !sitemap" class="empty-state">加载站点地图...</div>
      <div v-else-if="!sitemap && loadError" class="empty-state">{{ loadError }}</div>
      <div v-else-if="sitemap" class="sitemap">
        <div class="sitemap-meta">
          <span>{{ sitemap.host_count }} 个 Host</span>
          <span class="pager-sep">·</span>
          <span>{{ sitemap.endpoint_count }} 个端点</span>
          <span v-if="lastRefreshed" class="pager-sep">·</span>
          <span v-if="lastRefreshed">最近刷新 {{ lastRefreshed }}</span>
        </div>

        <div v-if="!sitemapHostList.length" class="empty-state">暂无站点结构。</div>
        <details
          v-for="host in sitemapHostList"
          :key="host"
          class="sitemap-host"
          :open="sitemapHostList.length <= 3"
        >
          <summary>{{ host }}</summary>
          <div v-for="(paths, method) in sitemap.hosts[host]" :key="host + method" class="sitemap-method">
            <div class="method-head">
              <span class="method" :data-method="method">{{ method }}</span>
              <span class="hint">{{ paths.length }} paths</span>
            </div>
            <ul>
              <li
                v-for="entry in paths"
                :key="entry.fingerprint"
                @click="openDetailFromSitemap(host, entry)"
              >
                <span class="path">{{ entry.path }}</span>
                <span class="hit">{{ entry.hit_count }}</span>
              </li>
            </ul>
          </div>
        </details>
      </div>
    </section>

    <div v-if="detailOpen" class="drawer-mask" @click.self="closeDetail">
      <aside class="drawer">
        <div class="drawer-top">
          <div>
            <div class="kicker">ENDPOINT</div>
            <h3>
              <span class="method" :data-method="detail?.method">{{ detail?.method }}</span>
              {{ detail?.path }}
            </h3>
            <p class="hint">{{ detail?.host }}</p>
            <p class="hint fingerprint">fingerprint: {{ detail?.fingerprint }}</p>
          </div>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>

        <div v-if="detailLoading" class="empty-state">加载详情...</div>
        <template v-else-if="detail">
          <div class="detail-grid">
            <div>
              <div class="detail-label">first_seen</div>
              <div>{{ detail.first_seen }}</div>
            </div>
            <div>
              <div class="detail-label">last_seen</div>
              <div>{{ detail.last_seen }}</div>
            </div>
            <div>
              <div class="detail-label">hit_count</div>
              <div>{{ detail.hit_count }}</div>
            </div>
          </div>

          <div v-if="detail.url_param_names?.length" class="detail-section">
            <div class="detail-label">URL 参数</div>
            <div class="tag-row">
              <span v-for="p in detail.url_param_names" :key="'u-' + p" class="tag">{{ p }}</span>
            </div>
          </div>

          <div v-if="detail.body_param_names?.length" class="detail-section">
            <div class="detail-label">Body 参数</div>
            <div class="tag-row">
              <span v-for="p in detail.body_param_names" :key="'b-' + p" class="tag">{{ p }}</span>
            </div>
          </div>

          <div v-if="statusCodeEntries.length" class="detail-section">
            <div class="detail-label">Status Codes</div>
            <div class="tag-row">
              <span v-for="[code, count] in statusCodeEntries" :key="code" class="status-tag">
                {{ code }} × {{ count }}
              </span>
            </div>
          </div>

          <div v-if="detail.content_types?.length" class="detail-section">
            <div class="detail-label">Content-Type</div>
            <div class="tag-row">
              <span v-for="ct in detail.content_types" :key="ct" class="tag muted">{{ ct }}</span>
            </div>
          </div>

          <div v-if="detail.auth_headers?.length" class="detail-section">
            <div class="detail-label">Auth Headers</div>
            <div class="tag-row">
              <span v-for="h in detail.auth_headers" :key="h" class="tag warn">{{ h }}</span>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-label">脱敏样本</div>
            <p v-if="!detail.sample" class="hint">暂无样本报文。</p>
            <article v-else class="packet">
              <header>
                <span>{{ detail.sample.captured_at }}</span>
                <span>packet #{{ detail.sample.packet_id }}</span>
              </header>
              <pre>{{ detail.sample.redacted_packet }}</pre>
            </article>
          </div>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { api } from "../api";

const props = defineProps({
  projectId: { type: Number, required: true },
  hosts: { type: Array, default: () => [] },
});

const tabs = [
  { id: "overview", label: "概览" },
  { id: "endpoints", label: "端点目录" },
  { id: "sitemap", label: "站点地图" },
];

const methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"];

const view = ref("overview");
const autoRefresh = ref(true);
const refreshInterval = ref(5);
const lastRefreshed = ref("");
const loadError = ref("");

const overview = ref(null);
const overviewLoading = ref(false);
const sinceInput = ref("");

const query = reactive({
  host: "",
  method: "",
  path_contains: "",
  q: "",
  since: "",
  sort: "last_seen",
  page: 1,
});
const listResult = ref({ items: [], total: 0, page: 1, page_size: 20 });
const listBusy = ref(false);

const sitemap = ref(null);
const sitemapHost = ref("");
const sitemapBusy = ref(false);

const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref(null);
const selectedFingerprint = ref("");
const selectedHost = ref("");

let refreshTimer = null;
let hostWatchPaused = false;

const totalItems = computed(() => listResult.value.total || 0);
const pageSize = computed(() => listResult.value.page_size || 20);
const currentPage = computed(() => listResult.value.page || query.page || 1);
const totalPages = computed(() => {
  if (totalItems.value === 0) return 0;
  return Math.ceil(totalItems.value / pageSize.value);
});
const canPrevPage = computed(() => currentPage.value > 1);
const canNextPage = computed(() => totalPages.value > 0 && currentPage.value < totalPages.value);
const displayPage = computed(() => (totalPages.value === 0 ? 0 : currentPage.value));

const newCount = computed(() => overview.value?.new_endpoints?.length || 0);

const sitemapHostList = computed(() => {
  if (!sitemap.value?.hosts) return [];
  return Object.keys(sitemap.value.hosts).sort();
});

const statusCodeEntries = computed(() => {
  const codes = detail.value?.status_codes || {};
  return Object.entries(codes).sort((a, b) => Number(a[0]) - Number(b[0]));
});

function formatNow() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function formatLoadError(err) {
  const msg = err?.message || String(err);
  if (/not found|404/i.test(msg)) {
    return "Recon API 不可用（404）：端口上的 API 进程过旧。请先执行 ./manage.sh stop，再 ./manage.sh dev。";
  }
  return msg;
}

function switchView(next) {
  view.value = next;
  setupRefreshTimer();
  refreshCurrent(false);
}

async function loadOverview(showNotice = false) {
  overviewLoading.value = true;
  try {
    overview.value = await api.recon({
      project_id: props.projectId,
      since: sinceInput.value || undefined,
      top: 30,
    });
    loadError.value = "";
    lastRefreshed.value = formatNow();
  } catch (err) {
    loadError.value = formatLoadError(err);
    if (showNotice) console.error(err);
  } finally {
    overviewLoading.value = false;
  }
}

function applySince() {
  loadOverview(true);
}

function clearSince() {
  sinceInput.value = "";
  loadOverview(true);
}

async function searchEndpoints(showNotice = false) {
  listBusy.value = true;
  try {
    listResult.value = await api.endpoints({
      project_id: props.projectId,
      host: query.host,
      method: query.method,
      path_contains: query.path_contains,
      q: query.q,
      since: query.since,
      sort: query.sort,
      page: query.page,
    });
    loadError.value = "";
    lastRefreshed.value = formatNow();
  } catch (err) {
    loadError.value = formatLoadError(err);
    if (showNotice) console.error(err);
  } finally {
    listBusy.value = false;
  }
}

async function loadSitemap(showNotice = false) {
  sitemapBusy.value = true;
  try {
    sitemap.value = await api.sitemap({
      project_id: props.projectId,
      host: sitemapHost.value || undefined,
    });
    loadError.value = "";
    lastRefreshed.value = formatNow();
  } catch (err) {
    loadError.value = formatLoadError(err);
    if (showNotice) console.error(err);
  } finally {
    sitemapBusy.value = false;
  }
}

function resetEndpointQuery() {
  hostWatchPaused = true;
  query.host = "";
  query.method = "";
  query.path_contains = "";
  query.q = "";
  query.since = "";
  query.sort = "last_seen";
  query.page = 1;
  hostWatchPaused = false;
  searchEndpoints(true);
}

function prevPage() {
  query.page = Math.max(1, query.page - 1);
  searchEndpoints(true);
}

function nextPage() {
  query.page += 1;
  searchEndpoints(true);
}

async function openDetail(row) {
  selectedFingerprint.value = row.fingerprint || row.unique_key;
  selectedHost.value = row.host;
  detailOpen.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    detail.value = await api.describeEndpoint({
      fingerprint: selectedFingerprint.value,
      host: selectedHost.value,
      project_id: props.projectId,
    });
  } finally {
    detailLoading.value = false;
  }
}

function openDetailFromSitemap(host, entry) {
  openDetail({ fingerprint: entry.fingerprint, host, method: "", path: entry.path });
}

function closeDetail() {
  detailOpen.value = false;
  detail.value = null;
  selectedFingerprint.value = "";
  selectedHost.value = "";
}

function refreshCurrent(showNotice = false) {
  if (view.value === "overview") return loadOverview(showNotice);
  if (view.value === "endpoints") return searchEndpoints(showNotice);
  return loadSitemap(showNotice);
}

function setupRefreshTimer() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = null;
  if (!autoRefresh.value) return;
  refreshTimer = setInterval(() => {
    if (view.value === "endpoints" && listBusy.value) return;
    if (view.value === "overview" && overviewLoading.value) return;
    if (view.value === "sitemap" && sitemapBusy.value) return;
    refreshCurrent(false);
  }, refreshInterval.value * 1000);
}

watch(
  () => query.host,
  (host, prev) => {
    if (hostWatchPaused || host === prev || view.value !== "endpoints") return;
    query.page = 1;
    searchEndpoints(false);
  },
);

watch(sitemapHost, () => {
  if (view.value === "sitemap") loadSitemap(false);
});

watch([autoRefresh, refreshInterval], setupRefreshTimer);

watch(
  () => props.projectId,
  () => {
    overview.value = null;
    sitemap.value = null;
    loadError.value = "";
    sinceInput.value = "";
    resetEndpointQuery();
    refreshCurrent(false);
  },
);

onMounted(async () => {
  await loadOverview(false);
  setupRefreshTimer();
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});
</script>

<style scoped>
.recon {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.recon-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.recon-error {
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px solid var(--danger);
  border-radius: 6px;
  color: var(--danger);
  background: rgba(255, 77, 58, 0.08);
  font-size: var(--font-size-sm);
}

.recon-nav {
  display: flex;
  gap: 6px;
}

.recon-tab {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  padding: 6px 12px;
  font-size: var(--font-size-sm);
  border-radius: 6px;
  cursor: pointer;
}

.recon-tab.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--btn-ghost-hover-bg);
}

.refresh-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: var(--font-size-sm);
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

.recon-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(80px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.summary-card {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--bg);
}

.summary-card b {
  color: var(--accent);
  font-size: 22px;
}

.summary-card span {
  color: var(--muted);
  font-size: var(--font-size-xs);
}

.overview-since {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-bottom: 12px;
}

.host-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag {
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--accent);
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: 999px;
}

.section-block {
  margin-bottom: 14px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}

.section-title h3 {
  margin: 0;
  font-family: var(--display);
  font-size: var(--font-size-md);
  color: var(--accent);
}

.hint,
.empty,
.empty-state {
  color: var(--muted);
  font-size: var(--font-size-sm);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
  margin-bottom: 10px;
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
  flex: 0 0 160px;
}

.filter-page {
  flex: 0 0 88px;
}

.filter-control {
  box-sizing: border-box;
  width: 100%;
  height: var(--control-height);
  min-height: var(--control-height);
  margin: 0;
  padding: 0 9px;
  line-height: 1.2;
  font-size: var(--font-size-sm);
  background: var(--input-bg);
  border: 1px solid var(--line);
  color: var(--ink);
  border-radius: 6px;
}

.filter-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: var(--control-height);
}

.btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  padding: 0 11px;
  min-height: var(--control-height);
  height: var(--control-height);
  font-size: var(--font-size-sm);
  border-radius: 6px;
  cursor: pointer;
}

.btn.lime {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--btn-primary-fg);
}

.btn.ghost:hover {
  background: var(--btn-ghost-hover-bg);
}

.table-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.table-head {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  margin-bottom: 6px;
  font-size: var(--font-size-sm);
}

.table-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--bg);
}

.table-scroll.compact {
  max-height: 240px;
  flex: none;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
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

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.active {
  background: var(--row-hover);
}

.path {
  word-break: break-all;
  color: var(--accent);
}

.params {
  max-width: 180px;
}

.param-tag {
  display: inline-block;
  margin: 0 4px 4px 0;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-2);
  color: var(--muted);
  font-size: var(--font-size-xs);
}

.param-tag.body {
  color: var(--warning);
}

.method {
  display: inline-block;
  min-width: 44px;
  text-align: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  background: var(--bg-2);
  color: var(--accent);
}

.method[data-method="GET"] {
  color: var(--notice);
}

.method[data-method="POST"],
.method[data-method="PUT"],
.method[data-method="PATCH"] {
  color: var(--warning);
}

.method[data-method="DELETE"] {
  color: var(--danger);
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
}

.pager-meta b {
  color: var(--accent);
}

.pager-sep {
  color: var(--line);
}

.pager .btn {
  width: 100%;
}

.sitemap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.sitemap-meta {
  color: var(--muted);
  font-size: var(--font-size-sm);
  margin-bottom: 10px;
}

.sitemap-host {
  border: 1px solid var(--line);
  border-radius: 6px;
  margin-bottom: 8px;
  background: var(--bg);
}

.sitemap-host summary {
  cursor: pointer;
  padding: 10px 12px;
  color: var(--accent);
  font-family: var(--display);
  list-style: none;
}

.sitemap-host summary::-webkit-details-marker {
  display: none;
}

.sitemap-method {
  padding: 0 12px 10px;
}

.method-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.sitemap-method ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.sitemap-method li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.sitemap-method li:hover {
  background: var(--row-hover);
}

.sitemap-method .hit {
  color: var(--muted);
  flex-shrink: 0;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  z-index: 30;
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: min(760px, 100%);
  height: 100%;
  overflow: auto;
  background: var(--modal-bg);
  border-left: 1px solid var(--line);
  padding: 18px;
}

.drawer-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.drawer-top h3 {
  margin: 4px 0 0;
  color: var(--accent);
  font-family: var(--display);
  word-break: break-all;
}

.kicker {
  color: var(--accent-dim);
  letter-spacing: 0.18em;
  font-size: var(--font-size-xs);
}

.fingerprint {
  margin-top: 6px;
  word-break: break-all;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.detail-label {
  color: var(--muted);
  font-size: var(--font-size-xs);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.detail-section {
  margin-bottom: 14px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag.muted {
  color: var(--muted);
}

.tag.warn {
  color: var(--warning);
}

.status-tag {
  border: 1px solid var(--line);
  padding: 3px 8px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  color: var(--ink);
}

.packet {
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}

.packet header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  color: var(--muted);
  background: var(--bg-2);
  font-size: var(--font-size-xs);
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
  font-size: var(--font-size-sm);
}

@media (max-width: 980px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
