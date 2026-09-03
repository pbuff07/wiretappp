# WIRETAPPP Agent 协作约束

本文档约束在本仓库内工作的 AI Agent / 开发者，确保 API 文档、MCP 与实现保持一致。

## 1. 项目概览

- **后端 API**：FastAPI，`backend/routers/` + `backend/main.py`
- **OpenAPI 规范**：项目根目录 `openapi.yaml`（权威接口文档）
- **MCP 服务**：`mcp/`（Go，stdio 传输，封装 REST API 供本地 AI 工具调用）
- **客户端**：Electron + Vue（`desktop/`、`frontend/`）

## 2. 单一事实来源

| 内容 | 位置 |
| --- | --- |
| HTTP 接口契约 | `openapi.yaml` |
| 用户文档 / 使用说明 | 根目录 `README.md`、`mcp/README.md` |
| 接口实现 | `backend/routers/*.py`、`backend/main.py` |
| Agent 端点聚合 | `backend/endpoints.py`、`backend/routers/recon.py` |
| MCP 工具定义 | `mcp/main.go`、`mcp/schemas.go`（须与 OpenAPI 能力对齐） |
| MCP 二进制 | `mcp/wiretappp-mcp`（本地编译产物，gitignore） |

## 3. 文档与变更约束

### 3.1 新增或修改 API 行为时

1. 先改 `backend/` 实现
2. **同步更新** `openapi.yaml`（路径、方法、参数、请求体、响应 schema、错误码）
3. 若该能力应对 AI 暴露，**同步更新 MCP**（见 [3.3](#33-mcp-同步与编译)）
4. **同步更新 README**（见 [3.4](#34-readme-同步)）
5. **重新编译 MCP 二进制**（见 [3.3](#33-mcp-同步与编译)）

### 3.2 OpenAPI 必须随功能变更更新

**无论修复 Bug 还是新增功能点，只要涉及 HTTP API 的任何变化（包括但不限于）：**

- 新增 / 删除 / 重命名路径或方法
- 查询参数、路径参数、请求体字段变更
- 响应结构、状态码、错误语义变更
- 默认值、校验规则、业务含义变更

**都必须在同一变更中更新 `openapi.yaml`。** 不允许「先改代码、文档后补」或遗漏文档。

### 3.3 MCP 同步与编译

**后端 API 有新增或行为变更时，须在同一变更中评估并同步 MCP，并编译出可用的 `wiretappp-mcp`。** 不允许只改 Python 侧、让 MCP 仍指向旧接口或旧二进制。

#### 须同步的文件

| 文件 | 内容 |
| --- | --- |
| `mcp/main.go` | 注册 tool：`Name`、`Description`、`InputSchema`、handler |
| `mcp/schemas.go` | 每个 tool 的 JSON Schema（`type: object` + `properties` + `required`） |
| `mcp/internal/wiretappp/client.go` | 仅当 HTTP 调用方式变化时（通常无需改） |
| `mcp/README.md` | Tools 对照表、Agent 工作流示例 |

> **go-sdk 要求**：`server.AddTool` 必须设置 `InputSchema`，否则启动即 panic（`missing input schema`）。

#### Agent / 开发者 checklist

1. 对照 `openapi.yaml` 确认 REST 路径、参数、必填项
2. 在 `main.go` 的 `registerTools` 增加或修改 tool 条目
3. 在 `schemas.go` 增加或修改对应 `InputSchema`（必填参数写入 `required`）
4. 更新 `mcp/README.md` 工具表
5. **执行编译**（见下方命令），确认无编译错误且启动自检通过
6. 若 Cursor / Claude 已配置 MCP，确认 `command` 指向本仓库的 `mcp/wiretappp-mcp`

#### 编译命令

```bash
# 推荐：带启动自检（检测 InputSchema 缺失等 panic）
./manage.sh mcp

# 或直接进入 mcp 目录
./mcp/build.sh
```

`./manage.sh install` 会在安装依赖后**自动编译 MCP**。变更 `mcp/*.go` 后应再次执行 `./manage.sh mcp`。

#### 设计原则

- 新增 REST 能力时，评估是否增加 MCP tool；渗透 recon 优先暴露语义化 tool（`wiretappp_recon_project`、`wiretappp_list_endpoints` 等）
- MCP 仅通过 HTTP 调用本机 API，不直连数据库
- Agent 集成应优先使用 `/api/endpoints`、`/api/sitemap`、`/api/recon`，避免直接拉取大量 `raw_packet`
- Tool 命名保持 `wiretappp_` 前缀，与 `openapi.yaml` 的 `operationId` / 路径语义一致

### 3.4 README 同步

**更新或优化功能时，须在同一变更中同步更新相关 README，避免文档与实现脱节。**

| 变更类型 | 须更新的文档 |
| --- | --- |
| API、捕获、配置、数据模型、启动方式 | 根目录 `README.md` |
| MCP 工具、环境变量、Agent 工作流 | `mcp/README.md` |
| Agent 协作规则、OpenAPI / MCP 约束 | `AGENT.md`（本文档） |
| 前端界面、项目工作区、Recon UI | 根目录 `README.md` |

须同步的内容包括但不限于：

- 命令与启动方式（如 `manage.sh` 子命令）
- 组件地址与架构说明（API / Vite / Electron / MCP）
- API 路径、参数、响应示例
- UI 功能入口与使用流程
- 项目结构目录树

**不允许「功能已上线、README 仍描述旧行为」。** 若仅做小范围修正，至少更新对应章节；若 README 与 `openapi.yaml` 冲突，以 `openapi.yaml` 为准并修正 README。

### 3.5 禁止事项

- 不要提交含密钥、证书私钥的变更
- 不要在不更新 `openapi.yaml` 的情况下合并 API 相关 PR
- 不要在不更新相关 README 的情况下合并用户可见的功能变更
- **不要只改 `backend/` 或 `openapi.yaml` 而不同步 MCP**（当该能力对 Agent 暴露时）
- **不要修改 `mcp/*.go` 后不执行 `./manage.sh mcp`**，避免本地仍运行旧版 `wiretappp-mcp`

## 4. 本地验证

```bash
# 安装依赖并编译 MCP
./manage.sh install

# 仅重新编译 MCP（改 mcp/ 后）
./manage.sh mcp

# 启动 API + Electron 开发
./manage.sh dev

# 对照 FastAPI 自动文档（运行时）
# http://127.0.0.1:18760/docs

# MCP 二进制启动自检（应无 panic，随后可 Ctrl+C）
./mcp/wiretappp-mcp
```

## 5. OpenAPI 编写约定

- 使用 OpenAPI 3.1
- `operationId` 与路径一一对应，camelCase
- 复用 `components/schemas` 与 `components/parameters`
- 中文 `summary` / `description` 与现有 README 术语一致
- 默认 server：`http://127.0.0.1:18760`
