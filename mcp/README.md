# WIRETAPPP MCP Server

Go 实现的 [Model Context Protocol](https://modelcontextprotocol.io/) 服务，通过 stdio 与 Cursor、Claude Desktop 等本地 AI 客户端通信，**只读**代理 WIRETAPPP 本机 REST API，供 Agent 查询已捕获的被动 HTTP 流量，用于渗透测试 recon 与分析参考。

> **权限模型**：MCP 仅暴露 `GET` 类查询接口。启动/暂停/停止捕获、修改配置、创建/删除项目等写操作不在 MCP 中提供，须由用户在 WIRETAPPP UI 或 `./manage.sh` 完成。

## 前置条件

1. WIRETAPPP API 已运行（例如 `./manage.sh dev` 或 Electron 已拉起后端）
2. 浏览器或系统代理已配置，且目标站点流量已被 WIRETAPPP 被动捕获
3. Go 1.22+

## 构建

```bash
# 推荐（含启动自检）
./manage.sh mcp

# 或在本目录
./build.sh
# GOPROXY=https://goproxy.cn,direct go build -o wiretappp-mcp .
```

编译产物：`mcp/wiretappp-mcp`（已 gitignore，改代码后须重新编译）。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WIRETAPPP_API_URL` | `http://127.0.0.1:18760` | WIRETAPPP API Base URL |

## Cursor 配置

在 Cursor Settings → MCP 中添加（路径改为本机绝对路径）：

```json
{
  "mcpServers": {
    "wiretappp": {
      "command": "/绝对路径/wiretappp/mcp/wiretappp-mcp",
      "env": {
        "WIRETAPPP_API_URL": "http://127.0.0.1:18760"
      }
    }
  }
}
```

## 提供的 Tools（只读）

### Recon — 渗透分析首选

| Tool | 对应 API | 说明 |
| --- | --- | --- |
| **`wiretappp_recon_project`** | `GET /api/recon` | 项目一键 recon：hosts + Top 端点 + sitemap 摘要 |
| **`wiretappp_list_endpoints`** | `GET /api/endpoints` | 结构化端点目录（API 地图），支持搜索与过滤 |
| **`wiretappp_describe_endpoint`** | `GET /api/endpoints/describe` | 端点详情 + 脱敏样本（status_codes、auth_headers） |
| **`wiretappp_sitemap`** | `GET /api/sitemap` | Host → Method → Path 站点地图 |
| **`wiretappp_whats_new`** | `GET /api/endpoints/new` | 自某时间以来新出现的端点 |

### 流量明细 — 次选

| Tool | 对应 API | 说明 |
| --- | --- | --- |
| `wiretappp_query_raw_packets` | `GET /api/packets?unique_key=...` | 原始 HTTP 报文（数据量大，优先用 describe） |
| `wiretappp_query_packet_keys` | `GET /api/packets`（keys 模式） | 低层唯一键列表，一般优先 `list_endpoints` |

### 项目与范围

| Tool | 对应 API |
| --- | --- |
| `wiretappp_list_projects` | `GET /api/projects` |
| `wiretappp_get_project` | `GET /api/projects/{id}` |
| `wiretappp_project_hosts` | `GET /api/projects/{id}/hosts` |
| `wiretappp_list_hosts` | `GET /api/hosts` |
| `wiretappp_dashboard` | `GET /api/dashboard` |

### 服务状态（只读）

| Tool | 对应 API |
| --- | --- |
| `wiretappp_health` | `GET /api/health` |
| `wiretappp_stats` | `GET /api/stats` |
| `wiretappp_capture_status` | `GET /api/capture/status` |
| `wiretappp_get_settings` | `GET /api/settings` |

完整 HTTP 契约见项目根目录 [`openapi.yaml`](../openapi.yaml)。

## Agent 推荐工作流

1. **`wiretappp_health`** — 确认 API 可用
2. **`wiretappp_list_projects`** — 确定 `project_id`
3. **`wiretappp_recon_project`** — 首轮攻击面摸底（hosts + Top 端点 + sitemap 摘要）
4. **`wiretappp_list_endpoints`** / **`wiretappp_sitemap`** / **`wiretappp_whats_new`** — 深入枚举或发现新路径
5. **`wiretappp_describe_endpoint`** — 查看脱敏样本（含 status_codes、auth_headers、参数名）
6. 仅在需要完整复现请求时，才使用 **`wiretappp_query_raw_packets`**

端点 `fingerprint` 即 `unique_key`（MD5），在 describe 与 raw 查询中通用。

## 给 Agent 的示例提示词

将以下提示词粘贴到已配置 WIRETAPPP MCP 的 Agent 对话中即可。Agent 会通过 MCP 工具链查询本地被动流量，无需你手动调 API。

### 示例 1：项目攻击面摸底

```
你正在协助我对 WIRETAPPP 已捕获的被动流量做渗透测试分析。WIRETAPPP MCP 已连接，只有只读查询权限，不能启动/停止捕获或修改配置。

请按顺序执行：
1. wiretappp_health 确认 API 可用
2. wiretappp_list_projects 列出项目，选定 project_id=1（若名称不符请告诉我）
3. wiretappp_recon_project(project_id=1, top=30) 获取攻击面概览
4. 根据 recon 结果，用 wiretappp_list_endpoints 搜索可疑端点（如 method=POST、path_contains=admin、q=upload）

输出：
- 已发现的 host 与子域
- Top API 端点列表（method + path + hit_count）
- 潜在高危面（管理接口、文件上传、认证相关）
- 建议的下一步测试方向
```

### 示例 2：针对特定 API 深入分析

```
WIRETAPPP MCP 已连接（只读）。目标项目 project_id=1，host=api.example.com。

请：
1. wiretappp_list_endpoints(project_id=1, host=api.example.com, sort=hit_count) 列出高频端点
2. 对 path 含 "user" 或 "auth" 的端点，逐个 wiretappp_describe_endpoint 查看脱敏样本
3. 总结：认证方式（Authorization/Cookie 等 header）、常见 status_codes、URL/body 参数名
4. 标出可能存在 IDOR、越权、信息泄露风险的端点及理由

不要拉取 raw_packet，除非 describe 样本不足以判断请求结构。
```

### 示例 3：增量发现新端点

```
WIRETAPPP MCP 只读模式。我昨天 18:00（UTC+8）后继续浏览了目标站，想对比是否有新 API。

请：
1. wiretappp_whats_new(since=2026-03-03T18:00:00+08:00, project_id=1)
2. 对新端点用 wiretappp_describe_endpoint 看脱敏样本
3. 列出新增 path、method，并评估是否值得手工测试
```

### 示例 4：确认捕获是否在跑

```
WIRETAPPP MCP 只读。请检查 wiretappp_capture_status 和 wiretappp_stats，告诉我捕获是否 running、当前有多少包和 host。若 stopped，提示我在 UI 或 manage.sh 中启动捕获，你不要尝试启动。
```

## 调用示例

项目 recon：

```json
{
  "name": "wiretappp_recon_project",
  "arguments": { "project_id": 1, "top": 30 }
}
```

搜索管理类端点：

```json
{
  "name": "wiretappp_list_endpoints",
  "arguments": {
    "project_id": 1,
    "method": "POST",
    "path_contains": "admin",
    "sort": "hit_count",
    "page_size": 20
  }
}
```

端点脱敏样本：

```json
{
  "name": "wiretappp_describe_endpoint",
  "arguments": {
    "fingerprint": "66f4b31f2daf0e2cbe4d74567dfe836f",
    "host": "api.example.com",
    "project_id": 1
  }
}
```

完整原始报文（次选）：

```json
{
  "name": "wiretappp_query_raw_packets",
  "arguments": {
    "host": "api.example.com",
    "unique_key": "66f4b31f2daf0e2cbe4d74567dfe836f",
    "page": 1,
    "page_size": 1
  }
}
```

## 开发说明

- 日志输出到 **stderr**（stdout 保留给 MCP JSON-RPC）
- MCP 连接时通过 `Instructions` 字段向 Agent 注入只读约束与推荐工作流
- 功能变更时须同步更新 `openapi.yaml`、本文档与 `mcp/main.go`，并执行 `./manage.sh mcp`（见 [`AGENT.md`](../AGENT.md) §3.3）
