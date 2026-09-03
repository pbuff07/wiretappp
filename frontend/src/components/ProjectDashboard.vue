<template>
  <div class="dashboard">
    <section class="dash-head panel">
      <div>
        <h2>项目看板</h2>
        <p class="hint">按域名范围聚合流量，点击进入项目查看明细。</p>
      </div>
      <div class="dash-actions">
        <button class="btn ghost" type="button" @click="$emit('open-settings')">系统设置</button>
        <button class="btn lime" type="button" @click="createOpen = true">新建项目</button>
      </div>
    </section>

    <section class="summary-row">
      <article class="summary-card panel">
        <span class="summary-label">项目总数</span>
        <strong>{{ dashboard.project_count || 0 }}</strong>
      </article>
      <article class="summary-card panel">
        <span class="summary-label">子域名合计</span>
        <strong>{{ totalSubdomains }}</strong>
      </article>
      <article class="summary-card panel">
        <span class="summary-label">唯一流量键合计</span>
        <strong>{{ totalUniqueKeys }}</strong>
      </article>
    </section>

    <section class="project-grid">
      <article
        v-for="item in dashboard.items"
        :key="item.id"
        class="project-card panel"
        @click="$emit('open', item.id)"
      >
        <div class="card-top">
          <h3>{{ item.name }}</h3>
          <div class="card-actions">
            <span class="created">{{ item.created_at }}</span>
            <button
              class="btn danger btn-sm"
              type="button"
              title="删除项目"
              @click.stop="confirmDelete(item)"
            >
              删除
            </button>
          </div>
        </div>
        <div class="domains">
          <span v-for="d in item.domains" :key="d" class="tag">{{ d }}</span>
        </div>
        <div class="metrics">
          <div><b>{{ item.subdomain_count }}</b><span>子域名</span></div>
          <div><b>{{ item.unique_key_count }}</b><span>唯一流量</span></div>
          <div><b>{{ item.packet_count }}</b><span>原始包</span></div>
        </div>
      </article>
      <article v-if="!dashboard.items?.length" class="empty-card panel">
        <p class="empty">还没有项目。点击「新建项目」开始。</p>
      </article>
    </section>

    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal">
        <div class="modal-top">
          <div>
            <div class="kicker">NEW PROJECT</div>
            <h3>新建项目</h3>
          </div>
          <button class="btn ghost" type="button" @click="createOpen = false">关闭</button>
        </div>
        <div class="field">
          <label>项目名称</label>
          <input v-model="form.name" placeholder="例如：Trustoken 充值测试" />
        </div>
        <div class="field">
          <label>域名范围（每行一个）</label>
          <textarea
            v-model="form.domainsText"
            rows="5"
            placeholder="trustoken.cn&#10;*.trustoken.cn&#10;api.example.com"
          ></textarea>
        </div>
        <p class="hint">
          `example.com` 匹配主域及全部子域；`*.example.com` 匹配该主域下所有子域；`api.example.com` 仅匹配该主机。
        </p>
        <p v-if="formError" class="error">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createOpen = false">取消</button>
          <button class="btn lime" :disabled="creating" type="button" @click="submitCreate">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { api } from "../api";

const emit = defineEmits(["open", "open-settings", "notice", "error"]);

const dashboard = ref({ project_count: 0, items: [] });
const createOpen = ref(false);
const creating = ref(false);
const deletingId = ref(null);
const formError = ref("");
const form = reactive({
  name: "",
  domainsText: "",
});
let refreshTimer = null;

const totalSubdomains = computed(() =>
  (dashboard.value.items || []).reduce((sum, item) => sum + (item.subdomain_count || 0), 0),
);
const totalUniqueKeys = computed(() =>
  (dashboard.value.items || []).reduce((sum, item) => sum + (item.unique_key_count || 0), 0),
);

async function loadDashboard() {
  dashboard.value = await api.dashboard();
}

function parseDomains(text) {
  return text
    .split(/[\n,;]+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

async function submitCreate() {
  formError.value = "";
  const domains = parseDomains(form.domainsText);
  if (!form.name.trim()) {
    formError.value = "请填写项目名称";
    return;
  }
  if (!domains.length) {
    formError.value = "请至少填写一个域名范围";
    return;
  }
  creating.value = true;
  try {
    const project = await api.createProject({ name: form.name.trim(), domains });
    createOpen.value = false;
    form.name = "";
    form.domainsText = "";
    await loadDashboard();
    emit("notice", `项目「${project.name}」已创建`);
    emit("open", project.id);
  } catch (err) {
    formError.value = err.message;
    emit("error", err.message);
  } finally {
    creating.value = false;
  }
}

async function confirmDelete(item) {
  const ok = window.confirm(
    `确定删除项目「${item.name}」？\n\n仅删除项目配置，已捕获的流量数据会保留在数据库中。`,
  );
  if (!ok) return;
  deletingId.value = item.id;
  try {
    await api.deleteProject(item.id);
    await loadDashboard();
    emit("notice", `项目「${item.name}」已删除`);
  } catch (err) {
    emit("error", err.message);
  } finally {
    deletingId.value = null;
  }
}

onMounted(() => {
  loadDashboard().catch((err) => emit("error", err.message));
  refreshTimer = setInterval(() => {
    if (createOpen.value || creating.value || deletingId.value) return;
    loadDashboard().catch(() => {});
  }, 3000);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});

defineExpose({ loadDashboard });
</script>

<style scoped>
.dashboard {
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

.dash-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
}

.dash-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.dash-head h2 {
  font-family: var(--display);
  font-size: var(--font-size-xl);
  color: var(--accent);
  margin: 0 0 6px;
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-label {
  color: var(--muted);
  font-size: var(--font-size-sm);
}

.summary-card strong {
  font-size: 28px;
  color: var(--accent);
  font-family: var(--display);
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.project-card {
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.project-card:hover {
  border-color: var(--accent);
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: start;
}

.card-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.card-top h3 {
  margin: 0;
  font-family: var(--display);
  color: var(--ink);
  font-size: var(--font-size-lg);
}

.created {
  color: var(--muted);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.btn-sm {
  min-height: 26px;
  padding: 0 8px;
  font-size: var(--font-size-xs);
}

.domains {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0;
}

.tag {
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--accent);
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: 999px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  border-top: 1px dashed var(--line);
  padding-top: 12px;
}

.metrics div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metrics b {
  color: var(--accent);
  font-size: var(--font-size-xl);
}

.metrics span {
  color: var(--muted);
  font-size: var(--font-size-xs);
}

.empty-card {
  grid-column: 1 / -1;
  padding: 28px;
  text-align: center;
}

.hint,
.empty {
  color: var(--muted);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
}

.error {
  color: var(--danger);
  font-size: var(--font-size-sm);
}

.btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  padding: 0 11px;
  font-size: var(--font-size-sm);
  border-radius: 6px;
  cursor: pointer;
  min-height: var(--control-height);
}

.btn.lime {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--btn-primary-fg);
}

.btn.ghost:hover {
  background: var(--btn-ghost-hover-bg);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--muted);
  font-size: var(--font-size-sm);
}

input,
textarea {
  background: var(--input-bg);
  border: 1px solid var(--line);
  color: var(--ink);
  padding: 8px 10px;
  border-radius: 6px;
  font-family: inherit;
  font-size: var(--font-size-sm);
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  width: min(520px, calc(100vw - 32px));
  background: var(--modal-bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: var(--shadow);
}

.modal-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.kicker {
  color: var(--accent-dim);
  letter-spacing: 0.18em;
  font-size: var(--font-size-xs);
}

h3 {
  margin: 0;
  color: var(--accent);
  font-family: var(--display);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 900px) {
  .summary-row {
    grid-template-columns: 1fr;
  }
}
</style>
