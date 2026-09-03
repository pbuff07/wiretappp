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

var api = wiretappp.NewClient()

func main() {
	log.SetOutput(os.Stderr)

	server := mcp.NewServer(&mcp.Implementation{
		Name:    "wiretappp",
		Version: "1.0.0",
	}, nil)

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
		{"wiretappp_health", "检查 WIRETAPPP API 是否可用，返回 local_url 等信息", schemaEmpty, handleGET("/api/health", nil)},
		{"wiretappp_stats", "获取全局捕获统计（包数、唯一键数、host 数）", schemaEmpty, handleGET("/api/stats", nil)},
		{"wiretappp_list_hosts", "列出已捕获 host；可选 project_id 限定项目范围", schemaProjectIDOptional, handleGET("/api/hosts", []string{"project_id"})},
		{"wiretappp_query_packet_keys", "按 host/时间/项目分页查询唯一流量键（mode=keys）", schemaPacketKeys, handleGET("/api/packets", []string{"host", "start", "end", "page", "page_size", "project_id"})},
		{"wiretappp_query_raw_packets", "按 unique_key(MD5 指纹) 查询原始 HTTP 报文（mode=raw）", schemaRawPackets, handleGET("/api/packets", []string{"unique_key", "host", "start", "end", "page", "page_size", "project_id"})},
		{"wiretappp_capture_status", "获取 mitm 捕获进程状态", schemaEmpty, handleGET("/api/capture/status", nil)},
		{"wiretappp_capture_start", "启动或恢复流量捕获", schemaEmpty, handlePOST("/api/capture/start")},
		{"wiretappp_capture_pause", "暂停入库（代理仍监听）", schemaEmpty, handlePOST("/api/capture/pause")},
		{"wiretappp_capture_resume", "恢复入库", schemaEmpty, handlePOST("/api/capture/resume")},
		{"wiretappp_capture_stop", "停止 mitm 捕获进程", schemaEmpty, handlePOST("/api/capture/stop")},
		{"wiretappp_get_settings", "读取代理监听、API、过滤后缀等配置", schemaEmpty, handleGET("/api/settings", nil)},
		{"wiretappp_update_settings", "更新配置（arguments.body 为 JSON 对象，字段均可选）", schemaUpdateSettings, handlePUT("/api/settings", "body")},
		{"wiretappp_dashboard", "项目看板：各项目子域名/唯一键/原始包统计", schemaEmpty, handleGET("/api/dashboard", nil)},
		{"wiretappp_list_projects", "列出所有项目", schemaEmpty, handleGET("/api/projects", nil)},
		{"wiretappp_get_project", "获取单个项目详情（arguments.project_id 必填）", schemaProjectIDRequired, handleGETPath("/api/projects/{project_id}", "project_id")},
		{"wiretappp_create_project", "创建项目，arguments.body: {name, domains[]}", schemaCreateProject, handlePOSTBody("/api/projects", "body")},
		{"wiretappp_delete_project", "删除项目配置（arguments.project_id 必填）", schemaProjectIDRequired, handleDELETEPath("/api/projects/{project_id}", "project_id")},
		{"wiretappp_project_hosts", "列出项目域名范围内的 host（arguments.project_id 必填）", schemaProjectIDRequired, handleGETPath("/api/projects/{project_id}/hosts", "project_id")},
		// Agent recon（优先使用）
		{"wiretappp_list_endpoints", "结构化端点目录（API 地图），支持 project_id/host/method/path_contains/q/since/sort", schemaListEndpoints, handleGET("/api/endpoints", []string{"project_id", "host", "method", "path_contains", "q", "since", "page", "page_size", "sort"})},
		{"wiretappp_describe_endpoint", "端点详情+脱敏样本（arguments.fingerprint + host 必填，include_raw 可选）", schemaDescribeEndpoint, handleGET("/api/endpoints/describe", []string{"fingerprint", "host", "project_id", "include_raw"})},
		{"wiretappp_sitemap", "Host→Method→Path 站点地图", schemaSitemap, handleGET("/api/sitemap", []string{"project_id", "host"})},
		{"wiretappp_whats_new", "自 since 以来新出现的端点（arguments.since 必填）", schemaWhatsNew, handleGET("/api/endpoints/new", []string{"since", "project_id", "host", "page", "page_size"})},
		{"wiretappp_recon_project", "项目一键 recon：hosts+sitemap 摘要+Top 端点+可选新端点（arguments.project_id 必填）", schemaReconProject, handleGET("/api/recon", []string{"project_id", "since", "top"})},
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

func handlePOST(path string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		data, err := api.Post(path, nil)
		if err != nil {
			return errResult(err)
		}
		return textResult(data)
	}
}

func handlePOSTBody(path, bodyKey string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := parseArgs(req.Params.Arguments)
		body, ok := args[bodyKey]
		if !ok {
			return errResult(fmt.Errorf("missing required argument: %s", bodyKey))
		}
		data, err := api.Post(path, body)
		if err != nil {
			return errResult(err)
		}
		return textResult(data)
	}
}

func handlePUT(path, bodyKey string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := parseArgs(req.Params.Arguments)
		body, ok := args[bodyKey]
		if !ok {
			return errResult(fmt.Errorf("missing required argument: %s", bodyKey))
		}
		data, err := api.Put(path, body)
		if err != nil {
			return errResult(err)
		}
		return textResult(data)
	}
}

func handleDELETEPath(pathTemplate, pathKey string) mcp.ToolHandler {
	return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := parseArgs(req.Params.Arguments)
		id, ok := args[pathKey]
		if !ok {
			return errResult(fmt.Errorf("missing required argument: %s", pathKey))
		}
		path := replacePath(pathTemplate, pathKey, id)
		data, err := api.Delete(path)
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
