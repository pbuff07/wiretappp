package wiretappp

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type Client struct {
	BaseURL    string
	HTTPClient *http.Client
}

func NewClient() *Client {
	base := strings.TrimRight(os.Getenv("WIRETAPPP_API_URL"), "/")
	if base == "" {
		base = "http://127.0.0.1:18760"
	}
	return &Client{
		BaseURL: base,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *Client) Get(path string, query url.Values) (json.RawMessage, error) {
	u := c.BaseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	return c.do(req)
}

func (c *Client) do(req *http.Request) (json.RawMessage, error) {
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("API %s %s -> %d: %s", req.Method, req.URL.Path, resp.StatusCode, strings.TrimSpace(string(data)))
	}
	if len(data) == 0 {
		return json.RawMessage("{}"), nil
	}
	if !json.Valid(data) {
		return json.RawMessage(fmt.Sprintf(`{"raw":%q}`, string(data))), nil
	}
	return json.RawMessage(data), nil
}

func QueryFromMap(params map[string]any, keys ...string) url.Values {
	q := url.Values{}
	for _, key := range keys {
		v, ok := params[key]
		if !ok || v == nil {
			continue
		}
		switch t := v.(type) {
		case string:
			if t != "" {
				q.Set(key, t)
			}
		case float64:
			q.Set(key, fmt.Sprintf("%g", t))
		case int:
			q.Set(key, fmt.Sprintf("%d", t))
		case bool:
			q.Set(key, fmt.Sprintf("%t", t))
		default:
			q.Set(key, fmt.Sprint(v))
		}
	}
	return q
}

func JSONText(data json.RawMessage) string {
	var buf bytes.Buffer
	if err := json.Indent(&buf, data, "", "  "); err != nil {
		return string(data)
	}
	return buf.String()
}
