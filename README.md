<div align="center">

# PageIndex Light MCP

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-v3-00ADD8?style=flat-square)](https://github.com/jlowin/fastmcp)
[![MCP](https://img.shields.io/badge/MCP-Compatible-8A2BE2?style=flat-square)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Agentic PDF Search via MCP — Inspired by [PageIndex](https://github.com/VectifyAI/PageIndex)**

*Vectorless, reasoning-based document retrieval that thinks like a human*

</div>

---

## Overview

PageIndex Light MCP brings **agentic search** capabilities to your PDF documents through the Model Context Protocol. Instead of traditional vector similarity, it leverages LLM reasoning for intelligent, human-like document navigation.

Inspired by [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) and [pageindex-mcp](https://github.com/VectifyAI/pageindex-mcp).

## Features

- **Agentic Search** — LLM-powered semantic search through document structure
- **MCP Sampling** — Native MCP protocol sampling support
- **LLM Fallback** — Auto-fallback to OpenAI-compatible APIs for non-sampling clients
- **OCR Fallback** — Automatic OCR for scanned PDFs

## Tools

| Tool | Description |
|------|-------------|
| `get_index` | Get PDF index with semantic search support |
| `get_detail` | Retrieve detailed content of a specific page |

## How It Works

```mermaid
flowchart TB
    subgraph Input
        A[PDF File] --> B{Text Extraction}
    end

    subgraph TextExtraction["Text Extraction"]
        B -->|Success| C[Raw Text]
        B -->|Empty/Minimal| D{OCR Configured?}
        D -->|Yes| E[Vision LLM OCR]
        D -->|No| C
        E --> C
    end

    subgraph Indexing
        C --> F[LLM Summarization]
        F -->|Per Page| G[Page Summaries]
        G --> H[(Cached Index)]
    end

    subgraph Search["Agentic Search"]
        I[User Query] --> J{Has Query?}
        J -->|No| K[Return Full Index]
        J -->|Yes| L[LLM Reasoning]
        H --> L
        L --> M[Ranked Results]
    end

    subgraph LLMProvider["LLM Provider"]
        N{MCP Sampling?}
        N -->|Supported| O[MCP Client LLM]
        N -->|Not Supported| P[Fallback LLM API]
    end

    F -.-> N
    L -.-> N
```

## Quick Start

### Claude Desktop / Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "pageindex": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/pageindex-light-mcp", "server.py"],
      "env": {
        "PAGEINDEX_LLM_BASE_URL": "https://api.openai.com/v1",
        "PAGEINDEX_LLM_API_KEY": "sk-xxx",
        "PAGEINDEX_LLM_MODEL": "gpt-4o-mini",
        "PAGEINDEX_OCR_BASE_URL": "https://api.openai.com/v1",
        "PAGEINDEX_OCR_API_KEY": "sk-xxx",
        "PAGEINDEX_OCR_MODEL": "gpt-4o-mini"
      }
    }
  }
}
```

### Environment Variables

Both configurations are **optional and independent**:

| Variable | Purpose | Required |
|----------|---------|----------|
| `PAGEINDEX_LLM_*` | Fallback for non-Sampling MCP clients | Optional |
| `PAGEINDEX_OCR_*` | Fallback for scanned PDFs (when text extraction fails) | Optional |

```bash
# LLM Config — Used when MCP client doesn't support Sampling
PAGEINDEX_LLM_BASE_URL=https://api.openai.com/v1
PAGEINDEX_LLM_API_KEY=sk-xxx
PAGEINDEX_LLM_MODEL=gpt-4o-mini

# OCR Config — Used when PDF text extraction returns empty/minimal content
PAGEINDEX_OCR_BASE_URL=https://api.openai.com/v1
PAGEINDEX_OCR_API_KEY=sk-xxx
PAGEINDEX_OCR_MODEL=gpt-4o-mini  # Any vision-capable model
```

## License

MIT
