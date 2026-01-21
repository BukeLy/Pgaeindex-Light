# PageIndex Light MCP

PDF 索引 MCP 服务，基于 FastMCP v3 构建。

## 功能特性

- **MCP Sampling** - 默认使用 MCP 协议的 Sampling 能力
- **LLM Fallback** - 不支持 Sampling 的客户端自动回退到 OpenAI 兼容 API
- **OCR Fallback** - 扫描版 PDF 自动调用 OCR 服务提取文本

## 环境变量

```bash
# LLM 配置 (Sampling 不可用时的 Fallback)
PAGEINDEX_LLM_BASE_URL=https://api.openai.com/v1
PAGEINDEX_LLM_API_KEY=sk-xxx
PAGEINDEX_LLM_MODEL=gpt-4o-mini

# OCR 配置 (文本提取失败时的 Fallback)
PAGEINDEX_OCR_BASE_URL=https://api.xxx.com/v1
PAGEINDEX_OCR_API_KEY=sk-xxx
PAGEINDEX_OCR_MODEL=ocr-model
```

## MCP 配置

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pageindex": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/Pgaeindex-Light", "server.py"],
      "env": {
        "PAGEINDEX_LLM_BASE_URL": "https://api.openai.com/v1",
        "PAGEINDEX_LLM_API_KEY": "sk-xxx",
        "PAGEINDEX_LLM_MODEL": "gpt-4o-mini",
        "PAGEINDEX_OCR_BASE_URL": "https://api.xxx.com/v1",
        "PAGEINDEX_OCR_API_KEY": "sk-xxx",
        "PAGEINDEX_OCR_MODEL": "ocr-model"
      }
    }
  }
}
```

## 使用方法

提供两个工具:

- `get_index` - 获取 PDF 索引，支持语义搜索
- `get_detail` - 获取指定页面的详细内容
