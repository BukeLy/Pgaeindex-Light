# PageIndex-Light 产品规划文档

## 1. 产品概述

### 1.1 产品定位
PageIndex-Light 是一个基于 FastMCP v3 的 Agentic Search MCP 服务，通过 VLM（Vision Language Model）对 PDF 文档进行页级索引，解决传统向量化搜索的"语义理解"困境。

### 1.2 核心价值
- **精准定位**：基于 VLM 生成的页面摘要进行语义搜索，而非简单的文本向量化
- **上下文完整**：保留完整页面图像，支持图表、公式等非文本内容的理解
- **两阶段检索**：先索引定位，后详情获取，降低 LLM 调用成本

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client (LLM)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastMCP v3 Server                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  get_index   │  │  get_detail  │  │  build_index     │  │
│  │    Tool      │  │    Tool      │  │    Tool          │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                              │                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Index Storage (JSON/SQLite)             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     VLM Provider                            │
│              (OpenAI GPT-4V / Claude Vision)                │
└─────────────────────────────────────────────────────────────┘
```

## 3. 功能规划

### 3.1 Tool: `get_index`
**功能**：获取 PDF 索引，支持 LLM 语义搜索

**输入参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | str | 是 | PDF 文件完整路径 |
| query | str | 否 | 搜索查询。如果提供，返回最相关页面；否则返回全部索引 |
| top_k | int | 否 | 返回结果数量，默认 5（仅在有 query 时生效） |

**处理流程**：
1. 检查索引缓存（基于文件哈希）
2. 若无缓存：解析 PDF → 逐页渲染图像 → VLM 生成摘要 → 保存索引
3. 若有 query：调用 LLM 对摘要进行语义搜索
4. 返回结果

**输出（无 query）**：
```json
{
  "status": "success",
  "file_path": "/path/to/doc.pdf",
  "total_pages": 42,
  "indexed_at": "2024-01-01T12:00:00",
  "pages": [
    {"page": 1, "text": "...", "summary": "..."},
    ...
  ]
}
```

**输出（有 query）**：
```json
{
  "status": "search",
  "file_path": "/path/to/doc.pdf",
  "query": "深度学习优化器",
  "total_pages": 42,
  "results": [
    {"page": 15, "relevance": "本页对比了 Adam、SGD 等优化器"},
    ...
  ]
}
```

**FastMCP v3 特性应用**：
- `task=True`：支持后台异步处理
- `Progress` 依赖：实时报告索引构建进度
- `Context.info()`：日志记录处理状态
- `Context.sample()`：调用 LLM 进行 OCR/摘要/搜索

### 3.2 Tool: `get_detail`
**功能**：获取指定页面的详细内容

**输入参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | str | 是 | PDF 文件完整路径 |
| page | int | 是 | 页码（从 1 开始） |

**输出**：
```json
{
  "file_path": "/path/to/doc.pdf",
  "page": 12,
  "text": "页面 OCR 文字内容...",
  "summary": "本页介绍了神经网络的反向传播算法...",
  "indexed_at": "2024-01-01T12:00:00"
}
```

**设计说明**：
- 返回已索引的文字和摘要
- LLM 根据 get_index 搜索结果决定获取哪些页面详情

## 4. 数据模型

### 4.1 索引存储结构
```python
class PageIndex(BaseModel):
    page_num: int
    image_base64: str
    summary: str
    created_at: datetime

class DocumentIndex(BaseModel):
    index_id: str
    file_path: str
    file_hash: str  # 用于检测文件变更
    total_pages: int
    pages: list[PageIndex]
    created_at: datetime
    updated_at: datetime
```

### 4.2 存储方案
- **开发环境**：JSON 文件存储（`~/.pageindex/cache/`）
- **生产环境**：SQLite + 文件系统（图像单独存储）

## 5. 技术实现

### 5.1 依赖库
```bash
uv add fastmcp pymupdf pillow
```

✅ **无需系统依赖**（如 poppler），纯 Python 安装即可。

### 5.2 核心代码结构
```
pageindex-light/
├── server.py               # FastMCP 服务入口（~15 行）
├── tools/                  # 工具模块（FileSystemProvider 自动发现）
│   ├── __init__.py
│   ├── indexing.py         # get_index 工具
│   └── detail.py           # get_detail 工具
├── shared/
│   ├── __init__.py
│   ├── pdf_utils.py        # PDF 处理工具
│   └── config.py           # 配置
└── ~/.pageindex/           # 索引缓存目录
```

### 5.3 FastMCP v3 特性应用

#### Lifespan - 初始化存储
```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    storage = await StorageService.initialize()
    yield {"storage": storage}
    await storage.close()

mcp = FastMCP("PageIndex-Light", lifespan=lifespan)
```

#### Background Task - 异步索引构建
```python
from fastmcp import FastMCP
from fastmcp.server.dependencies import Progress

@mcp.tool(task=True)
async def build_index(
    file_path: str,
    progress: Progress = Progress()
) -> dict:
    pages = parse_pdf(file_path)
    progress.set_total(len(pages))

    for i, page in enumerate(pages):
        await process_page(page)
        progress.increment()
        progress.set_message(f"Processing page {i+1}/{len(pages)}")

    return {"status": "success", "total_pages": len(pages)}
```

#### Context - 日志与状态
```python
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

@mcp.tool
async def get_index(
    file_path: str,
    query: str,
    ctx: Context = CurrentContext()
) -> dict:
    await ctx.info(f"Searching index for: {query}")
    storage = ctx.lifespan_context["storage"]
    results = await storage.search(file_path, query)
    return {"results": results}
```

## 6. 使用流程

### 6.1 典型交互流程
```
User: "帮我分析这个 PDF 文档：/path/to/research.pdf"

LLM → get_index(file_path="/path/to/research.pdf")
      ← {"status": "success", "total_pages": 42, "pages": [...]}

User: "文档中关于'深度学习优化器'的内容在哪里？"

LLM → get_index(file_path="/path/to/research.pdf", query="深度学习优化器")
      ← {"status": "search", "results": [{"page": 15, "relevance": "本页对比了Adam、SGD等优化器"}]}

LLM: "根据索引，第15页包含相关内容，让我获取详情..."

LLM → get_detail(file_path="/path/to/research.pdf", page=15)
      ← {"page": 15, "text": "...", "summary": "..."}

LLM: "根据第15页内容，深度学习优化器主要包括..."
```

## 7. 配置项

### 7.1 环境变量
```bash
# VLM 配置
PAGEINDEX_VLM_PROVIDER=openai          # openai / anthropic
PAGEINDEX_VLM_API_KEY=sk-xxx
PAGEINDEX_VLM_MODEL=gpt-4o             # 或 claude-3-5-sonnet

# 存储配置
PAGEINDEX_STORAGE_PATH=~/.pageindex/cache
PAGEINDEX_MAX_CACHE_SIZE=10GB

# 性能配置
PAGEINDEX_MAX_CONCURRENT_PAGES=5       # 并发处理页数
PAGEINDEX_IMAGE_DPI=150                # 图像渲染 DPI
PAGEINDEX_IMAGE_FORMAT=png             # png / jpeg
```

## 8. 里程碑

### Phase 1: MVP
- [ ] 基础 PDF 解析与图像提取（pymupdf）
- [ ] VLM 摘要生成（ctx.sample）
- [ ] JSON 文件存储
- [ ] 两个核心 Tool 实现（get_index + get_detail）
- [ ] LLM 语义搜索（query 参数）

### Phase 2: 增强
- [ ] 索引缓存与增量更新
- [ ] 进度报告完善
- [ ] 并发锁保护

### Phase 3: 生产化
- [ ] 错误处理与重试机制
- [ ] 单元测试与集成测试
- [ ] 文档与示例

## 9. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| VLM 调用成本高 | 大文档索引费用高 | 支持本地 VLM、缓存策略 |
| PDF 解析兼容性 | 部分 PDF 无法解析 | 多库 fallback、错误报告 |
| 图像大小过大 | Token 消耗高 | 自适应压缩、分辨率控制 |
| 索引搜索准确度 | 检索结果不相关 | 优化 prompt、支持重排序 |
