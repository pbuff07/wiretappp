# WIRETAPPP MCP Server

Go 实现的 [Model Context Protocol](https://modelcontextprotocol.io/) 服务，通过 stdio 与 Cursor、Claude Desktop 等本地 AI 客户端通信，代理调用 WIRETAPPP 本机 REST API 查询与控制被动流量捕获。

## 前置条件

1. WIRETAPPP API 已运行（例如 `./manage.sh dev` 或 Electron 已拉起后端）
2. Go 1.22+

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
      "command": "/绝对路径/pentest-mitm/mcp/wiretappp-mcp",
      "env": {
        "WIRETAPPP_API_URL": "http://127.0.0.1:18760"
      }
    }
  }
}
```

## 提供的 Tools

| Tool | 对应 API |
| --- | --- |
| `wiretappp_health` | `GET /api/health` |
| `wiretappp_stats` | `GET /api/stats` |
| `wiretappp_list_hosts` | `GET /api/hosts` |
| `wiretappp_query_packet_keys` | `GET /api/packets`（唯一键模式） |
| `wiretappp_query_raw_packets` | `GET /api/packets?unique_key=...` |
| `wiretappp_capture_status` | `GET /api/capture/status` |
| `wiretappp_capture_start` | `POST /api/capture/start` |
| `wiretappp_capture_pause` | `POST /api/capture/pause` |
| `wiretappp_capture_resume` | `POST /api/capture/resume` |
| `wiretappp_capture_stop` | `POST /api/capture/stop` |
| `wiretappp_get_settings` | `GET /api/settings` |
| `wiretappp_update_settings` | `PUT /api/settings`（`arguments.body`） |
| `wiretappp_dashboard` | `GET /api/dashboard` |
| `wiretappp_list_projects` | `GET /api/projects` |
| `wiretappp_get_project` | `GET /api/projects/{id}` |
| `wiretappp_create_project` | `POST /api/projects`（`arguments.body`） |
| `wiretappp_delete_project` | `DELETE /api/projects/{id}` |
| `wiretappp_project_hosts` | `GET /api/projects/{id}/hosts` |
| **`wiretappp_list_endpoints`** | `GET /api/endpoints`（**Agent 首选**） |
| **`wiretappp_describe_endpoint`** | `GET /api/endpoints/describe` |
| **`wiretappp_sitemap`** | `GET /api/sitemap` |
| **`wiretappp_whats_new`** | `GET /api/endpoints/new` |
| **`wiretappp_recon_project`** | `GET /api/recon` |

完整 HTTP 契约见项目根目录 [`openapi.yaml`](../openapi.yaml)。

## Agent 推荐工作流

1. **`wiretappp_recon_project`** — 首轮了解项目攻击面（hosts + Top 端点 + sitemap 摘要）
2. **`wiretappp_sitemap`** — 查看完整 path 结构
3. **`wiretappp_list_endpoints`** / **`wiretappp_whats_new`** — 搜索或发现新路径
4. **`wiretappp_describe_endpoint`** — 获取单端点脱敏样本（含 status_codes、auth_headers）
5. 需要完整复现时再使用 `wiretappp_query_raw_packets`

```json
{
  "name": "wiretappp_recon_project",
  "arguments": { "project_id": 1, "top": 30 }
}
```

## 调用示例

查询某 host 的唯一流量键：

```json
{
  "name": "wiretappp_query_packet_keys",
  "arguments": {
    "host": "www.example.com",
    "page": 1,
    "page_size": 20
  }
}
```

获取原始报文（需先从上一步拿到 `unique_key` MD5 指纹）：

```json
{
  "name": "wiretappp_query_raw_packets",
  "arguments": {
    "host": "www.example.com",
    "unique_key": "66f4b31f2daf0e2cbe4d74567dfe836f",
    "page": 1,
    "page_size": 1
  }
}
```

## 开发说明

- 日志输出到 **stderr**（stdout 保留给 MCP JSON-RPC）
- 功能变更时须同步更新 `openapi.yaml`、相关 README 与 MCP 工具，并执行 `./manage.sh mcp`（见 [`AGENT.md`](../AGENT.md) §3.3）
