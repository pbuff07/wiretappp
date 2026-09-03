# WIRETAPPP · 被动流量捕获与查询

基于 **mitmproxy + FastAPI + Vue + Electron** 的本机浏览器流量被动捕获系统。通过本地 HTTP/HTTPS 代理拦截浏览器流量，过滤静态资源后，将业务请求按指纹入库；提供 **Electron 桌面客户端**、**REST API** 与 **MCP 服务**（供 AI Agent 调用）。

| 组件 | 默认地址 | 说明 |
| --- | --- | --- |
| REST API | `http://127.0.0.1:18760` | 查询、配置、捕获控制、Recon |
| 局域网 API | `http://<本机IP>:18760` | 同网段调用 `/api/*`，无需鉴权 |
| Electron + Vue UI | `http://127.0.0.1:5173` | 开发模式下 Vite 页面，由 Electron 加载 |
| 代理监听 | `127.0.0.1:8080` | 浏览器 HTTP/HTTPS 代理 |
| 数据存储 | `data/packets.db`（开发） / `~/.wiretappp/data/`（打包后） | SQLite，WAL 模式 |
| OpenAPI / Swagger | `http://127.0.0.1:18760/docs` | 权威接口文档；规范文件见 `openapi.yaml` |
| MCP 服务 | stdio | Go 实现，见 [`mcp/README.md`](mcp/README.md) |

> 若本机 `18760` 端口被占用，可在 `config.yaml` 中修改 `api_port`。

---

## 目录

- [快速开始](#快速开始)
- [客户端界面](#客户端界面)
- [浏览器接入](#浏览器接入)
- [数据模型与唯一键](#数据模型与唯一键)
- [原始报文存储格式](#原始报文存储格式)
- [配置说明](#配置说明)
- [manage.sh 命令](#manage-sh-命令)
- [API 概览](#api-概览)
- [接口详情](#接口详情)
  - [健康检查](#1-健康检查)
  - [下载 CA 证书](#2-下载-ca-证书)
  - [查询流量](#3-查询流量)
  - [Host 列表](#4-host-列表)
  - [统计信息](#5-统计信息)
  - [捕获状态](#6-捕获状态)
  - [捕获控制](#7-捕获控制)
  - [读取/更新配置](#8-读取更新配置)
  - [项目管理](#9-项目管理)
  - [攻击面 Recon](#10-攻击面-recon)
- [MCP 与 AI Agent](#mcp-与-ai-agent)
- [错误响应](#错误响应)
- [调用示例](#调用示例)
- [项目结构](#项目结构)

---

## 快速开始

```bash
chmod +x manage.sh
./manage.sh install   # 安装 Python / 前端 / Electron 依赖
./manage.sh dev       # 启动 Electron（自动拉起 API + Vite 开发服务器）
./manage.sh stop      # 停止后台 mitm 进程（如有）
```

Electron 窗口打开后即可使用项目看板；API 默认监听 `http://127.0.0.1:18760`。

**API 访问方式（无需鉴权）：**

| 场景 | 地址 |
| --- | --- |
| 本机脚本 / MCP | `http://127.0.0.1:18760` |
| 局域网其他机器 | `http://<本机IP>:18760`（`GET /api/health` 返回 `lan_urls`） |

默认 `api_host: 0.0.0.0`，监听所有网卡。

将浏览器代理设置为 `127.0.0.1:8080`，安装并信任 mitm CA 证书后即可开始捕获。

---

## 客户端界面

Electron 桌面客户端加载 Vite 开发页面（`127.0.0.1:5173`），后端 API **不提供**静态 Web 托管。

| 页面 | 入口 | 功能 |
| --- | --- | --- |
| 项目看板 | 启动后默认 | 创建 / 打开项目，查看全局统计 |
| 系统设置 | 看板顶栏「设置」 | 捕获控制、监听端口、静态过滤、主题 |
| 项目工作区 | 点击项目卡片 | 侧边栏：捕获 / 监听 / 静态过滤；主区 Tab：**流量查询**、**攻击面 Recon** |

**攻击面 Recon**（项目工作区主区 Tab）：

- **概览** — Host / 端点统计、Top 端点、可选 since 新端点
- **端点目录** — 按 method / path / host 筛选，查看参数名与命中次数
- **站点地图** — Host → Method → Path 树形结构
- 点击端点行可查看脱敏样本（status codes、auth headers 等）

捕获默认**不自动启动**，需在项目侧边栏或系统设置中手动点击「启动」。

---

## 浏览器接入

1. 执行 `./manage.sh dev` 启动 Electron 客户端。
2. 在项目侧边栏或系统设置中 **启动捕获**，然后点击 **下载 mitm CA 证书**，或访问 `GET /api/ca-cert`。
3. **macOS**：钥匙串访问 → 导入证书 → 对「安全套接字层 (SSL)」设为 **始终信任**（**只需信任一次**）。
4. **Chrome / Edge**：系统代理设置为 `127.0.0.1:8080`（HTTP 与 HTTPS 均走代理）。
5. 访问目标站点，业务 API 流量会自动入库。

CA 证书与 mitm 密钥持久保存在用户目录（不随项目路径变化）：

| 系统 | 证书路径 |
| --- | --- |
| macOS | `~/.wiretappp/data/mitmproxy/mitmproxy-ca-cert.pem` |
| Linux | `$XDG_CONFIG_HOME/wiretappp/data/mitmproxy/mitmproxy-ca-cert.pem` |
| Windows | `%APPDATA%\wiretappp\data\mitmproxy\mitmproxy-ca-cert.pem` |

系统设置页会显示完整路径；首次启动捕获后生成，之后在系统中信任一次即可长期复用。

> 仅用于授权范围内的本机渗透/调试场景，请勿用于未授权流量拦截。

---

## 数据模型与唯一键

每条捕获记录包含：

| 字段 | 说明 |
| --- | --- |
| `captured_at` | 捕获时间，ISO8601，**UTC+8** |
| `host` | 请求 Host（不含端口） |
| `unique_key` | 业务指纹键（**MD5 十六进制**，32 字符） |
| `key_label` | 人类可读标签，如 `POST /api/x · url(a,b) · body(c)` |
| `method` | HTTP 方法 |
| `path` | 路径（不含 query） |
| `raw_packet` | 完整可读 HTTP 报文（请求 + 响应） |

### 唯一键规则

内部先构造 canonical 字符串（legacy 格式），再取其 **MD5** 作为 `unique_key` 入库；`key_label` 用于 UI 与 Recon 展示。

**Canonical 格式（仅作 MD5 输入，不直接存库）：**

```text
METHOD @$ PATH @$ url_para_<query参数名排序> @$ body_para_<body参数名排序>
```

规则：

- `PATH` 为 URL 路径，**不含** query string。
- `url_para_` 后为 query 参数**名**的去重排序列表，逗号拼接；无参数时为 `url_para_`。
- `body_para_` 后为 body 参数**名**的去重排序列表：
  - `application/json`：取 JSON 顶层 key；
  - `application/x-www-form-urlencoded`：取表单字段名；
  - 无 body 或无参数时为 `body_para_`。
- 参数**值不参与**指纹计算，相同接口不同参数值会归为同一键。

**key_label 示例：**

```text
POST /api/login · url(-) · body(password,username)
GET /api/user · url(id,sort) · body(-)
```

### 示例

| 请求 | unique_key（MD5） | key_label |
| --- | --- | --- |
| `GET /api/user?id=1&sort=desc` | `a1b2c3...`（32 位 hex） | `GET /api/user · url(id,sort) · body(-)` |
| `POST /api/login` body `{"username":"a","password":"b"}` | `d4e5f6...` | `POST /api/login · url(-) · body(password,username)` |

查询原始报文时使用 `unique_key`（MD5 指纹）；Recon 接口中的 `fingerprint` 字段与之相同。

---

## 原始报文存储格式

`raw_packet` 为可读文本，结构如下：

```text
===== REQUEST =====
POST /api/user/topup/quote HTTP/1.1
Host: www.example.com
Content-Type: application/json
...

{"amount":300}

===== RESPONSE =====
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 574
...

{"success":true,"data":{...}}
```

说明：

- 响应 body 使用 **解压后的明文**（自动处理 gzip / br / zstd 等），不会存储乱码压缩流。
- 展示时会移除 `Content-Encoding`、`Transfer-Encoding`，并按解压后 body 重算 `Content-Length`。
- 单条 body 超过 `max_body_bytes`（默认 512KB）时会截断并附加 `[truncated N bytes]` 提示。

---

## 配置说明

配置文件位置（按优先级自动创建/读取）：

| 系统 | 路径 |
| --- | --- |
| macOS | `~/.wiretappp/config.yaml` |
| Linux | `$XDG_CONFIG_HOME/wiretappp/config.yaml` |
| Windows | `%APPDATA%\wiretappp\config.yaml` |

项目根目录的 `config.yaml` 作为首次启动时的默认模板。示例内容：

```yaml
listen_host: 127.0.0.1      # mitm 代理监听地址
listen_port: 8080           # mitm 代理监听端口
api_host: 0.0.0.0           # FastAPI 绑定地址（0.0.0.0 允许局域网访问）
api_port: 18760             # FastAPI 端口
static_suffixes:            # 静态资源后缀，匹配则丢弃不入库
  - .js
  - .css
  - .png
  # ...
max_body_bytes: 524288      # 单条 body 最大存储字节
```

可通过项目工作区侧边栏、系统设置页或 `PUT /api/settings` 修改。修改 `listen_host` / `listen_port` 后，若 mitm 已在运行会自动重启。

---

## manage.sh 命令

| 命令 | 作用 |
| --- | --- |
| `install` | 安装 Python / 前端 / Electron 依赖，并编译 MCP |
| `dev` | 启动 Electron 开发调试（自动拉起 API + Vite） |
| `pack` | 打包桌面应用（可选 `--platform` / `--arch`） |
| `mcp` | 编译 MCP 二进制（`mcp/wiretappp-mcp`，含启动自检） |
| `stop` | 停止 mitm、API（18760）、Vite（5173） |

### 打包桌面应用

```bash
./manage.sh pack                              # 当前平台 + 架构
./manage.sh pack --platform mac --arch arm64  # macOS Apple Silicon
./manage.sh pack --platform mac --arch x64    # macOS Intel
./manage.sh pack --platform linux --arch x64
./manage.sh pack --platform win --arch x64
./manage.sh pack --help
```

产物输出到 `desktop/dist/`（如 macOS 的 `.dmg` / `.zip`）。

打包后的应用首次启动会在用户目录创建配置（若不存在则从内置默认复制）：

| 系统 | 配置路径 |
| --- | --- |
| macOS | `~/.wiretappp/config.yaml` |
| Linux | `$XDG_CONFIG_HOME/wiretappp/config.yaml`（默认 `~/.config/wiretappp/`） |
| Windows | `%APPDATA%\wiretappp\config.yaml` |

开发模式下配置文件同样优先读取上述用户目录；捕获数据与日志仍在项目根目录 `data/`、`logs/`。打包后数据、日志、运行态文件也迁移至用户目录。

> 跨平台交叉打包时，Electron 壳可跨平台构建，但 **Python 运行时仅能在本机同平台/架构下打包**。交叉打包会跳过 Python bundle，需在目标系统重新安装依赖。

### 日志目录

- `logs/api.log` — API 服务日志
- `logs/mitm.log` — mitmproxy 日志
- `logs/capture.log` — 捕获插件日志

打包后日志位于用户目录 `~/.wiretappp/logs/`（或各平台等价路径）。

---

## API 概览

**Base URL**：

- 本机：`http://127.0.0.1:18760`
- 局域网：`http://<本机IP>:18760`（`GET /api/health` 返回 `lan_urls`）

端口以 `config.yaml` 中 `api_port` 为准；默认 `api_host: 0.0.0.0` 允许局域网访问，**无鉴权**。

**通用约定**：

- 请求/响应均为 JSON（`/api/ca-cert` 除外）。
- 时间参数使用 ISO8601，推荐带时区，如 `2026-08-20T09:00:00+08:00`；不带时区时按 UTC+8 解析。
- 分页参数：`page` 从 1 开始，`page_size` 默认 20，最大 100。
- 完整契约见项目根目录 [`openapi.yaml`](openapi.yaml)；Agent 协作约束见 [`AGENT.md`](AGENT.md)。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/ca-cert` | 下载 mitm CA 证书 |
| GET | `/api/packets` | 查询唯一键或原始报文 |
| GET | `/api/hosts` | 已捕获 host 列表（支持 `project_id`） |
| GET | `/api/stats` | 库内统计 |
| GET | `/api/dashboard` | 看板聚合统计 |
| GET/POST | `/api/projects` | 项目列表 / 创建 |
| GET/DELETE | `/api/projects/{id}` | 项目详情 / 删除 |
| GET | `/api/projects/{id}/hosts` | 项目范围内 host |
| GET | `/api/endpoints` | 结构化端点目录（Recon） |
| GET | `/api/endpoints/new` | 自 since 以来新端点 |
| GET | `/api/endpoints/describe` | 端点详情 + 脱敏样本 |
| GET | `/api/sitemap` | Host → Method → Path 站点地图 |
| GET | `/api/recon` | 项目一键 recon 聚合 |
| GET | `/api/capture/status` | 捕获进程状态 |
| POST | `/api/capture/start` | 启动/恢复捕获 |
| POST | `/api/capture/pause` | 暂停入库 |
| POST | `/api/capture/resume` | 恢复入库 |
| POST | `/api/capture/stop` | 停止 mitm 捕获 |
| GET | `/api/settings` | 读取配置 |
| PUT | `/api/settings` | 更新配置 |

---

## 接口详情

### 1. 健康检查

```http
GET /api/health
```

**响应 200**

```json
{
  "ok": true,
  "api_host": "0.0.0.0",
  "api_port": 18760,
  "local_url": "http://127.0.0.1:18760",
  "lan_urls": ["http://192.168.1.23:18760"],
  "bind_host": "0.0.0.0",
  "port": 18760
}
```

---

### 2. 下载 CA 证书

```http
GET /api/ca-cert
```

**响应 200**：PEM 文件流，`Content-Disposition: mitmproxy-ca-cert.pem`

**响应 404**（mitm 尚未启动、CA 未生成）

```json
{
  "ready": false,
  "detail": "CA 尚未生成，请先启动捕获"
}
```

---

### 3. 查询流量

```http
GET /api/packets
```

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `host` | string | 否 | 按 host 精确过滤，如 `www.trustoken.cn` |
| `start` | string | 否 | 开始时间（UTC+8），`captured_at >= start` |
| `end` | string | 否 | 结束时间（UTC+8），`captured_at <= end` |
| `page` | int | 否 | 页码，默认 `1` |
| `page_size` | int | 否 | 每页条数，默认 `20`，最大 `100` |
| `unique_key` | string | 否 | **传入则返回原始报文**；不传则只返回唯一键聚合 |

#### 3.1 查询唯一键（默认）

```http
GET /api/packets?host=www.trustoken.cn&page=1&page_size=20
```

**响应 200**

```json
{
  "mode": "keys",
  "page": 1,
  "page_size": 20,
  "total": 8,
  "items": [
    {
      "unique_key": "66f4b31f2daf0e2cbe4d74567dfe836f",
      "key_label": "POST /api/user/topup/quote · url(-) · body(amount)",
      "host": "www.trustoken.cn",
      "first_seen": "2026-08-20T17:10:38+08:00",
      "last_seen": "2026-08-20T17:35:38+08:00",
      "hit_count": 3
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `mode` | 固定为 `"keys"` |
| `total` | 符合条件的 `(unique_key, host)` 组合总数 |
| `items[].first_seen` | 该键首次出现时间 |
| `items[].last_seen` | 该键最近出现时间 |
| `items[].hit_count` | 命中次数 |
| `items[].key_label` | 人类可读标签 |
| `items[].unique_key` | MD5 指纹，查询 raw 时使用 |

#### 3.2 查询原始报文

`unique_key` 为 MD5 指纹（32 位 hex），可直接传入 query。

**去重规则：** 同一 `unique_key` 下，若多条记录的 `raw_packet` 内容完全相同，接口只返回 **1 条**，并附带 `hit_count` 表示重复捕获次数。`captured_at` 为最近一次捕获时间，`first_seen` 为最早一次。

```http
GET /api/packets?host=www.trustoken.cn&unique_key=66f4b31f2daf0e2cbe4d74567dfe836f&page=1
```

**响应 200**

```json
{
  "mode": "raw",
  "page": 1,
  "page_size": 20,
  "total": 1,
  "items": [
    {
      "id": 15,
      "first_seen": "2026-08-20T10:01:00+08:00",
      "captured_at": "2026-08-20T17:35:38+08:00",
      "host": "www.trustoken.cn",
      "unique_key": "66f4b31f2daf0e2cbe4d74567dfe836f",
      "key_label": "POST /api/user/topup/quote · url(-) · body(amount)",
      "method": "POST",
      "path": "/api/user/topup/quote",
      "raw_packet": "===== REQUEST =====\nPOST /api/user/topup/quote HTTP/1.1\r\n...",
      "hit_count": 12
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `mode` | 固定为 `"raw"` |
| `total` | 去重后的原始报文条数（按 `host + raw_packet` 分组） |
| `items[].raw_packet` | 完整可读 HTTP 请求 + 响应文本 |
| `items[].hit_count` | 该报文内容被捕获的次数 |
| `items[].captured_at` | 最近一次捕获时间 |
| `items[].first_seen` | 最早一次捕获时间 |

---

### 4. Host 列表

```http
GET /api/hosts
```

**响应 200**

```json
{
  "items": [
    "www.trustoken.cn",
    "api.example.com"
  ]
}
```

按捕获条数降序排列。

---

### 5. 统计信息

```http
GET /api/stats
```

**响应 200**

```json
{
  "packet_count": 16,
  "unique_key_count": 8,
  "host_count": 2,
  "latest_captured_at": "2026-08-20T17:35:38+08:00"
}
```

| 字段 | 说明 |
| --- | --- |
| `packet_count` | 原始包总数 |
| `unique_key_count` | 唯一键（按 host 分组）数量 |
| `host_count` | 不同 host 数量 |
| `latest_captured_at` | 最近一次捕获时间，无数据时为 `null` |

---

### 6. 捕获状态

```http
GET /api/capture/status
```

**响应 200**

```json
{
  "status": "running",
  "paused": false,
  "pid": 86987,
  "listen_host": "127.0.0.1",
  "listen_port": 8080,
  "mitm_confdir": "/Users/you/.wiretappp/data/mitmproxy",
  "ca_cert_ready": true,
  "ca_cert_path": "/Users/you/.wiretappp/data/mitmproxy/mitmproxy-ca-cert.pem",
  "static_suffixes": [".js", ".css", ".png"]
}
```

| 字段 | 说明 |
| --- | --- |
| `status` | `running` 捕获中 / `paused` 已暂停 / `stopped` 未运行 |
| `paused` | 是否处于暂停入库状态 |
| `pid` | mitm 进程 PID，未运行时为 `null` |
| `mitm_confdir` | mitmproxy confdir，CA 持久化目录 |
| `ca_cert_path` | CA 证书 PEM 完整路径（固定于用户目录） |

---

### 7. 捕获控制

#### 启动 / 恢复捕获

```http
POST /api/capture/start
```

若 mitm 已在运行则清除暂停标志并恢复入库；若未运行则启动 mitm 进程。

**响应 200**：同 [捕获状态](#6-捕获状态) 结构。

**响应 500**（mitm 启动失败）

```json
{
  "detail": "mitm 进程启动失败，详见 logs/mitm.log"
}
```

#### 暂停入库

```http
POST /api/capture/pause
```

代理继续监听，但不再写入数据库。

**响应 200**：捕获状态对象。

**响应 409**（mitm 未运行）

```json
{
  "detail": "捕获进程未运行"
}
```

#### 恢复入库

```http
POST /api/capture/resume
```

**响应 200 / 409**：同 pause。

#### 停止 mitm

```http
POST /api/capture/stop
```

停止 mitm 捕获进程（API 服务本身不受影响）。

**响应 200**：捕获状态对象（`status` 为 `stopped`）。

---

### 8. 读取/更新配置

#### 读取

```http
GET /api/settings
```

**响应 200**

```json
{
  "listen_host": "127.0.0.1",
  "listen_port": 8080,
  "api_host": "127.0.0.1",
  "api_port": 18760,
  "static_suffixes": [".js", ".css", ".png"],
  "max_body_bytes": 524288
}
```

#### 更新

```http
PUT /api/settings
Content-Type: application/json
```

**请求体**（字段均可选，只更新传入项）

```json
{
  "listen_host": "127.0.0.1",
  "listen_port": 8080,
  "static_suffixes": [".js", ".css", ".woff2"],
  "max_body_bytes": 524288
}
```

| 字段 | 约束 |
| --- | --- |
| `listen_port` | 1–65535 |
| `static_suffixes` | 字符串数组；可写 `js` 或 `.js`，会自动补点前缀 |
| `max_body_bytes` | ≥ 1024 |

**响应 200**

```json
{
  "settings": {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "api_host": "127.0.0.1",
    "api_port": 18760,
    "static_suffixes": [".js", ".css", ".woff2"],
    "max_body_bytes": 524288
  },
  "mitm_restarted": true,
  "capture": {
    "status": "running",
    "paused": false,
    "pid": 86987,
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "ca_cert_ready": true,
    "ca_cert_path": "...",
    "static_suffixes": [".js", ".css", ".woff2"]
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `mitm_restarted` | 监听地址变更且 mitm 在跑时为 `true` |
| `capture` | 更新后的捕获状态 |

> `api_host` / `api_port` 仅可通过 `config.yaml` 修改，需重启 `./manage.sh dev` 后生效。

---

### 9. 项目管理

项目用于按域名范围隔离流量查询与 Recon。

```http
GET /api/projects
POST /api/projects
GET /api/projects/{project_id}
DELETE /api/projects/{project_id}
GET /api/projects/{project_id}/hosts
GET /api/dashboard
```

创建项目请求体示例：

```json
{
  "name": "示例站点",
  "domains": ["example.com", "*.api.example.com"]
}
```

查询流量、端点、站点地图时均可传 `project_id` 限定范围。详见 [`openapi.yaml`](openapi.yaml) `projects` tag。

---

### 10. 攻击面 Recon

面向渗透 recon 的结构化 API，**Agent / MCP 应优先使用**，避免直接拉取大量 `raw_packet`。

| 路径 | 说明 |
| --- | --- |
| `GET /api/recon?project_id=` | 一键聚合：hosts、sitemap 摘要、Top 端点、可选新端点 |
| `GET /api/endpoints` | 端点目录，支持 host / method / path_contains / q / since / sort |
| `GET /api/endpoints/new?since=` | 自某时间以来首次出现的端点 |
| `GET /api/endpoints/describe?fingerprint=&host=` | 端点详情 + 脱敏样本（status_codes、auth_headers） |
| `GET /api/sitemap` | Host → Method → Path 树 |

端点项主要字段：`fingerprint`（同 `unique_key`）、`method`、`path`、`url_param_names`、`body_param_names`、`hit_count`。

`describe` 返回的 `sample.redacted_packet` 已对 Authorization、Cookie 等敏感头脱敏。

UI 入口：项目工作区 → **攻击面 Recon** Tab。

---

## MCP 与 AI Agent

[`mcp/`](mcp/) 提供 Go 实现的 MCP stdio 服务，封装 REST API 供 Cursor、Claude Desktop 等本地 AI 工具调用。

```bash
cd mcp && go build -o wiretappp-mcp .
```

常用 Recon 工具（完整列表见 [`mcp/README.md`](mcp/README.md)）：

| Tool | API |
| --- | --- |
| `wiretappp_recon_project` | `GET /api/recon` |
| `wiretappp_list_endpoints` | `GET /api/endpoints` |
| `wiretappp_describe_endpoint` | `GET /api/endpoints/describe` |
| `wiretappp_sitemap` | `GET /api/sitemap` |
| `wiretappp_whats_new` | `GET /api/endpoints/new` |

推荐工作流：先 `wiretappp_recon_project` 了解攻击面 → `wiretappp_sitemap` / `wiretappp_list_endpoints` 深入 → `wiretappp_describe_endpoint` 看脱敏样本 → 需要完整复现时再 `wiretappp_query_raw_packets`。

开发约束见 [`AGENT.md`](AGENT.md)（OpenAPI、MCP、README 须与代码同步更新）。

---

## 错误响应

FastAPI 标准错误格式：

```json
{
  "detail": "错误描述"
}
```

| HTTP 状态码 | 常见场景 |
| --- | --- |
| 404 | 路径不存在；CA 证书未就绪；端点 / 项目不存在 |
| 409 | 捕获进程未运行时调用 pause/resume |
| 422 | 请求参数校验失败 |
| 500 | mitm 启动失败等内部错误 |

---

## 调用示例

### curl — 按 host 查唯一键

```bash
curl -s 'http://127.0.0.1:18760/api/packets?host=www.trustoken.cn&page=1' | jq .
```

### curl — 按时间范围查询

```bash
curl -sG 'http://127.0.0.1:18760/api/packets' \
  --data-urlencode 'host=www.trustoken.cn' \
  --data-urlencode 'start=2026-08-20T00:00:00+08:00' \
  --data-urlencode 'end=2026-08-20T23:59:59+08:00' \
  --data-urlencode 'page=1' | jq .
```

### curl — 获取原始报文

```bash
FINGERPRINT='66f4b31f2daf0e2cbe4d74567dfe836f'
curl -sG 'http://127.0.0.1:18760/api/packets' \
  --data-urlencode "host=www.trustoken.cn" \
  --data-urlencode "unique_key=${FINGERPRINT}" | jq '.items[0].raw_packet'
```

### curl — 项目 Recon 概览

```bash
curl -sG 'http://127.0.0.1:18760/api/recon' \
  --data-urlencode 'project_id=1' \
  --data-urlencode 'top=20' | jq .
```

### curl — 端点目录

```bash
curl -sG 'http://127.0.0.1:18760/api/endpoints' \
  --data-urlencode 'project_id=1' \
  --data-urlencode 'method=POST' \
  --data-urlencode 'sort=hit_count' | jq .
```

### curl — 端点详情（脱敏样本）

```bash
curl -sG 'http://127.0.0.1:18760/api/endpoints/describe' \
  --data-urlencode 'project_id=1' \
  --data-urlencode 'host=www.example.com' \
  --data-urlencode 'fingerprint=66f4b31f2daf0e2cbe4d74567dfe836f' | jq .
```

### curl — 暂停 / 恢复捕获

```bash
curl -s -X POST 'http://127.0.0.1:18760/api/capture/pause'
curl -s -X POST 'http://127.0.0.1:18760/api/capture/resume'
```

### curl — 更新静态后缀

```bash
curl -s -X PUT 'http://127.0.0.1:18760/api/settings' \
  -H 'Content-Type: application/json' \
  -d '{"static_suffixes":[".js",".css",".map",".woff2"]}' | jq .
```

### Python

```python
import requests

BASE = "http://127.0.0.1:18760"

# 查询某 host 的唯一键
r = requests.get(f"{BASE}/api/packets", params={
    "host": "www.trustoken.cn",
    "page": 1,
})
keys = r.json()["items"]

# 拉取第一条的原始报文
if keys:
    raw = requests.get(f"{BASE}/api/packets", params={
        "host": keys[0]["host"],
        "unique_key": keys[0]["unique_key"],  # MD5 指纹
        "page": 1,
    }).json()
    print(raw["items"][0]["raw_packet"])

# Recon：项目攻击面概览
recon = requests.get(f"{BASE}/api/recon", params={"project_id": 1, "top": 20}).json()
print(recon["sitemap_summary"], recon["top_endpoints"][:3])
```

---

## 项目结构

```text
pentest-mitm/
├── backend/           # FastAPI + mitm 捕获插件
│   ├── capture_addon.py
│   ├── database.py
│   ├── endpoints.py   # Recon 聚合服务
│   ├── main.py
│   └── routers/
├── frontend/          # Vue 控制台（Vite）
├── desktop/           # Electron 桌面壳
│   ├── assets/        # Logo / favicon 源图
│   ├── build/         # 打包图标与 Python bundle（生成）
│   └── scripts/       # 图标生成脚本
├── mcp/               # Go MCP stdio 服务
├── openapi.yaml       # OpenAPI 3.1 权威契约
├── AGENT.md           # Agent 协作约束
├── config.yaml        # 运行配置
├── manage.sh          # install / dev / pack / stop
├── data/
│   ├── packets.db     # SQLite 数据库
│   └── mitmproxy/     # mitm CA 与 confdir
└── logs/              # 运行日志
```
