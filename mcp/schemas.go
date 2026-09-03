package main

import "github.com/google/jsonschema-go/jsonschema"

func emptyObjectSchema() *jsonschema.Schema {
	return &jsonschema.Schema{Type: "object"}
}

func objectSchema(properties map[string]*jsonschema.Schema, required ...string) *jsonschema.Schema {
	s := &jsonschema.Schema{
		Type:       "object",
		Properties: properties,
	}
	if len(required) > 0 {
		s.Required = required
	}
	return s
}

func strProp(desc string) *jsonschema.Schema {
	return &jsonschema.Schema{Type: "string", Description: desc}
}

func intProp(desc string) *jsonschema.Schema {
	return &jsonschema.Schema{Type: "integer", Description: desc}
}

func boolProp(desc string) *jsonschema.Schema {
	return &jsonschema.Schema{Type: "boolean", Description: desc}
}

var (
	schemaEmpty = emptyObjectSchema()

	schemaProjectIDOptional = objectSchema(map[string]*jsonschema.Schema{
		"project_id": intProp("项目 ID"),
	})

	schemaPacketKeys = objectSchema(map[string]*jsonschema.Schema{
		"host":        strProp("Host 精确过滤"),
		"start":       strProp("开始时间（UTC+8，ISO8601）"),
		"end":         strProp("结束时间（UTC+8，ISO8601）"),
		"page":        intProp("页码，从 1 开始"),
		"page_size":   intProp("每页条数，最大 100"),
		"project_id":  intProp("项目 ID"),
	})

	schemaRawPackets = objectSchema(map[string]*jsonschema.Schema{
		"unique_key":  strProp("端点 MD5 指纹（与 list_endpoints 返回的 fingerprint 相同）"),
		"host":        strProp("Host"),
		"start":       strProp("开始时间（UTC+8，ISO8601）"),
		"end":         strProp("结束时间（UTC+8，ISO8601）"),
		"page":        intProp("页码，从 1 开始"),
		"page_size":   intProp("每页条数，最大 100"),
		"project_id":  intProp("项目 ID"),
	}, "unique_key")

	schemaProjectIDRequired = objectSchema(map[string]*jsonschema.Schema{
		"project_id": intProp("项目 ID"),
	}, "project_id")

	schemaListEndpoints = objectSchema(map[string]*jsonschema.Schema{
		"project_id":    intProp("项目 ID"),
		"host":          strProp("Host 过滤"),
		"method":        strProp("HTTP 方法"),
		"path_contains": strProp("path 子串"),
		"q":             strProp("搜索 path / host / key_label"),
		"since":         strProp("仅 first_seen >= since（UTC+8）"),
		"page":          intProp("页码"),
		"page_size":     intProp("每页条数"),
		"sort":          strProp("last_seen | first_seen | hit_count"),
	})

	schemaDescribeEndpoint = objectSchema(map[string]*jsonschema.Schema{
		"fingerprint":  strProp("端点 MD5 指纹（来自 list_endpoints / recon）"),
		"host":         strProp("Host"),
		"project_id":   intProp("项目 ID"),
		"include_raw":  boolProp("默认 false（脱敏样本）；true 时返回完整 raw_packet"),
	}, "fingerprint", "host")

	schemaSitemap = objectSchema(map[string]*jsonschema.Schema{
		"project_id": intProp("项目 ID"),
		"host":       strProp("Host 过滤"),
	})

	schemaWhatsNew = objectSchema(map[string]*jsonschema.Schema{
		"since":       strProp("起始时间（UTC+8，ISO8601）"),
		"project_id":  intProp("项目 ID"),
		"host":        strProp("Host 过滤"),
		"page":        intProp("页码"),
		"page_size":   intProp("每页条数"),
	}, "since")

	schemaReconProject = objectSchema(map[string]*jsonschema.Schema{
		"project_id": intProp("项目 ID"),
		"since":      strProp("若提供则附带此时间后的新端点"),
		"top":        intProp("Top N 端点数量，1-100"),
	}, "project_id")
)
