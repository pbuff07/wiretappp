package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/google/jsonschema-go/jsonschema"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/zengyizhan/wiretappp-mcp/internal/wiretappp"
)

const serverInstructions = `WIRETAPPP MCP 为只读查询服务：可读取本机已捕获的被动 HTTP 流量，用于渗透测试 recon 与分析参考。
禁止尝试启动/停止/暂停捕获、修改配置或增删项目；这些操作须由用户在 WIRETAPPP UI 或 manage.sh 完成。

推荐查询顺序：
1. wiretappp_health → wiretappp_list_projects 确认服务与目标项目
2. wiretappp_recon_project 获取攻击面概览（hosts、Top 端点、sitemap 摘要）
3. wiretappp_list_endpoints / wiretappp_sitemap / wiretappp_whats_new 深入枚举
4. wiretappp_describe_endpoint 查看脱敏样本（status_codes、auth_headers、参数名）
5. 仅在需要完整复现请求时，才用 wiretappp_query_raw_packets（默认优先 describe 的 redacted_packet）

端点 fingerprint 即 unique_key（MD5），describe 与 raw 查询共用。`

var api = wiretappp.NewClient()

func main() {
	log.SetOutput(os.Stderr)

	server := mcp.NewServer(&mcp.Implementation{
		Name:        "wiretappp",
		Title:       "WIRETAPPP Passive Traffic Reader",
		Description: "Read-only MCP for locally captured passive HTTP traffic (pentest recon).",
		Version:     "1.1.0",
	}, &mcp.ServerOptions{
		Instructions: serverInstructions,
	})

	registerTools(server)

	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		log.Fatal(err)
	}
}

func registerTools(server *mcp.Server) {
	type toolDef struct {
		name        string
		description string
		schema      *jsonschema.Schema
		handler     mcp.ToolHandler
	}

	tools := []toolDef{
		// Recon — primary pentest workflow
		{"wiretappp_recon_project", "【首选】项目一键 recon：hosts、sitemap 摘要、Top 端点、可选 since 后的新端点。渗透首轮攻击面摸底。", schemaReconProject, handleGET("/api/recon", []string{"project_id", "since", "top"})},
		{"wiretappp_list_endpoints", "【首选】结构化端点目录（API 地图）：method/path/参数名/fingerprint/hit_count。支持 host、method、path_contains、q、since、sort 过滤。", schemaListEndpoints, handleGET("/api/endpoints", []string{"project_id", "host", "method", "path_contains", "q", "since", "page", "page_size", "sort"})},
		{"wiretappp_describe_endpoint", "端点详情与脱敏样本（status_codes、auth_headers、参数示例）。默认脱敏；include_raw=true 才返回完整 raw_packet。", schemaDescribeEndpoint, handleGET("/api/endpoints/describe", []string{"fingerprint", "host", "project_id", "include_raw"})},
		{"wiretappp_sitemap", "Host → Method → Path 站点地图，快速浏览路径结构与覆盖范围。", schemaSitemap, handleGET("/api/sitemap", []string{"project_id", "host"})},
		{"wiretappp_whats_new", "自 since 以来首次出现的新端点，适合增量测试或对比前后流量变化。", schemaWhatsNew, handleGET("/api/endpoints/new", []string{"since", "project_id", "host", "page", "page_size"})},

		// Traffic detail — use when recon tools are insufficient
		{"wiretappp_query_raw_packets", "按 fingerprint(unique_key) 拉取原始 HTTP 报文。数据量大、含敏感信息，仅在 describe 脱敏样本不足以复现请求时使用。", schemaRawPackets, handleGET("/api/packets", []string{"unique_key", "host", "start", "end", "page", "page_size", "project_id"})},
		{"wiretappp_query_packet_keys", "低层唯一流量键列表（host/时间/项目分页）。一般优先 wiretappp_list_endpoints；仅在需要 keys 模式时使用。", schemaPacketKeys, handleGET("/api/packets", []string{"host", "start", "end", "page", "page_size", "project_id"})},

		// Project & scope context
		{"wiretappp_list_projects", "列出所有项目（含 id、name、domains），确定 project_id 后再做 recon。", schemaEmpty, handleGET("/api/projects", nil)},
		{"wiretappp_get_project", "单个项目详情（domains、统计等）。", schemaProjectIDRequired, handleGETPath("/api/projects/{project_id}", "project_id")},
		{"wiretappp_project_hosts", "项目域名范围内已捕获的 host 列表。", schemaProjectIDRequired, handleGETPath("/api/projects/{project_id}/hosts", "project_id")},
		{"wiretappp_list_hosts", "全局 host 列表；可选 project_id 限定项目范围。", schemaProjectIDOptional, handleGET("/api/hosts", []string{"project_id"})},
		{"wiretappp_dashboard", "各项目子域名/唯一键/原始包统计概览。", schemaEmpty, handleGET("/api/dashboard", nil)},

		// Service context (read-only)
		{"wiretappp_health", "检查 WIRETAPPP API 是否可用，返回 local_url 等信息。", schemaEmpty, handleGET("/api/health", nil)},
		{"wiretappp_stats", "全局捕获统计：包数、唯一键数、host 数。", schemaEmpty, handleGET("/api/stats", nil)},
		{"wiretappp_capture_status", "只读：当前 mitm 捕获进程状态（running/paused/stopped）。", schemaEmpty, handleGET("/api/capture/status", nil)},
		{"wiretappp_get_settings", "只读：代理监听、过滤后缀等配置，帮助理解哪些流量可能被忽略。", schemaEmpty, handleGET("/api/settings", nil)},
	}

	for _, t := range tools {
		server.AddTool(&mcp.Tool{
			Name:        t.name,
			Description: t.description,
			InputSchema: t.schema,
		}, t.handler)
	}
}

func parseArgs(raw json.RawMessage) map[string]any {
	if len(raw) == 0 {
		return map[string]any{}
	}
	var args map[string]any
	if err := json.Unmarshal(raw, &args); err != nil {
		return map[string]any{}
	}
	return args
}

func textResult(data json.RawMessage) (*mcp.CallToolResult, error) {
	return &mcp.CallToolResult{
		Content: []mcp.Content{
			&mcp.TextContent{Text: wiretappp.JSONText(data)},
		},
	}, nil
}

func errResult(err error) (*mcp.CallToolResult, error) {
	return &mcp.CallToolResult{
		IsError: true,
		Content: []mcp.Content{
			&mcp.TextContent{Text: err.Error()},
		},
	}, nil
}

func handleGET(path string, queryKeys []string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := parseArgs(req.Params.Arguments)
		q := wiretappp.QueryFromMap(args, queryKeys...)
		data, err := api.Get(path, q)
		if err != nil {
			return errResult(err)
		}
		return textResult(data)
	}
}

func handleGETPath(pathTemplate, pathKey string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := parseArgs(req.Params.Arguments)
		id, ok := args[pathKey]
		if !ok {
			return errResult(fmt.Errorf("missing required argument: %s", pathKey))
		}
		path := replacePath(pathTemplate, pathKey, id)
		data, err := api.Get(path, nil)
		if err != nil {
			return errResult(err)
		}
		return textResult(data)
	}
}

func replacePath(template, key string, value any) string {
	placeholder := "{" + key + "}"
	switch v := value.(type) {
	case float64:
		return strings.Replace(template, placeholder, fmt.Sprintf("%.0f", v), 1)
	default:
		return strings.Replace(template, placeholder, fmt.Sprint(v), 1)
	}
}
