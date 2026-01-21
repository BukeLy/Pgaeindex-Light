# PageIndex-Light 实现方案（FastMCP v3 Provider 架构）

## 🎯 目标
使用 FastMCP v3 的 Provider 架构实现解耦的 PDF 索引服务。

## 📁 目录结构
```
pageindex-light/
├── server.py               # 主服务器（极简）
├── providers/
│   ├── __init__.py
│   └── pdf_provider.py     # PDF 索引 Provider
├── tools/                  # 工具模块（FileSystemProvider 自动发现）
│   ├── __init__.py
│   ├── indexing.py         # 索引工具
│   └── detail.py           # 详情工具
├── shared/
│   ├── __init__.py
│   ├── pdf_utils.py        # PDF 处理工具
│   └── config.py           # 配置
└── ~/.pageindex/           # 索引缓存目录
```

---

## 📝 实现代码

### 1️⃣ 主服务器（server.py）- 极简

```python
from fastmcp import FastMCP
from fastmcp.providers import FileSystemProvider
from pathlib import Path

mcp = FastMCP(
    name="PDF索引助手",
    instructions="PDF 文档索引服务，支持 OCR 和内容摘要"
)

# v3: FileSystemProvider 自动发现 tools/ 下的工具
tools_provider = FileSystemProvider(
    root_path=Path(__file__).parent / "tools",
    reload=True  # 开发模式：热重载
)

mcp.add_provider(tools_provider)

if __name__ == "__main__":
    mcp.run()
```

**优势**：主文件只有 ~15 行，工具自动发现。

---

### 2️⃣ 配置模块（shared/config.py）

```python
from pathlib import Path

INDEX_DIR = Path.home() / ".pageindex"
INDEX_DIR.mkdir(exist_ok=True)
```

---

### 3️⃣ PDF 工具模块（shared/pdf_utils.py）

```python
from pathlib import Path
from PIL import Image
import fitz  # pymupdf - 无需系统依赖
import base64
import io
import hashlib
import json

def get_pdf_hash(pdf_path: Path) -> str:
    """计算文件哈希"""
    with open(pdf_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def get_index_path(pdf_path: Path) -> Path:
    """获取索引文件路径"""
    from shared.config import INDEX_DIR
    path_hash = hashlib.md5(str(pdf_path.absolute()).encode()).hexdigest()[:12]
    return INDEX_DIR / f"{pdf_path.stem}_{path_hash}.json"


def extract_page_as_image(pdf_path: Path, page_num: int) -> Image.Image:
    """PDF 页面转图片（使用 pymupdf，无需 poppler）"""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"页码 {page_num} 超出范围 [0, {len(doc)-1}]")
        page = doc[page_num]
        pix = page.get_pixmap(dpi=150)
        return pix.pil_image()  # 官方推荐方式，比 Image.frombytes 更稳定
    finally:
        if doc:
            doc.close()


def get_total_pages(pdf_path: Path) -> int:
    """获取 PDF 总页数"""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        return len(doc)
    except Exception as e:
        raise RuntimeError(f"无法打开 PDF: {pdf_path}, 错误: {e}")
    finally:
        if doc:
            doc.close()


def image_to_base64(image: Image.Image) -> str:
    """图片转 base64"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def load_index(pdf_path: Path) -> dict | None:
    """加载索引"""
    index_path = get_index_path(pdf_path)
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_index(pdf_path: Path, index_data: dict):
    """保存索引"""
    index_path = get_index_path(pdf_path)
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
```

---

### 4️⃣ 索引工具（tools/indexing.py）

```python
from fastmcp import tool
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext, Progress
from pathlib import Path
from datetime import datetime
from asyncio import Lock
import json

from shared.pdf_utils import (
    get_pdf_hash,
    extract_page_as_image,
    image_to_base64,
    load_index,
    save_index,
    get_total_pages
)

# 并发锁：防止同一文件被重复索引
_indexing_locks: dict[str, Lock] = {}


async def ocr_and_summarize(image_b64: str, page_num: int, ctx: Context) -> dict:
    """用 LLM 做 OCR 和总结"""
    response = await ctx.sample(
        f"""识别图片中的文字，并用1-2句话总结内容。
返回JSON格式：
{{"text": "识别的文字", "summary": "内容总结"}}""",
        image=f"data:image/png;base64,{image_b64}"
    )

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {"text": response, "summary": "解析失败"}

    result['page'] = page_num
    return result


async def search_with_llm(query: str, pages: list[dict], ctx: Context, top_k: int = 5) -> list[dict]:
    """用 LLM 对索引进行语义搜索"""
    # 构建摘要列表
    summaries = "\n".join([
        f"第{p['page']}页: {p.get('summary', '无摘要')}"
        for p in pages if not p.get('error')
    ])

    response = await ctx.sample(
        f"""根据用户查询，从以下页面摘要中找出最相关的页面。

用户查询: {query}

页面摘要列表:
{summaries}

请返回最相关的页码（最多{top_k}个），按相关性排序。
返回JSON格式：
{{"results": [{{"page": 页码, "relevance": "相关原因"}}]}}"""
    )

    try:
        result = json.loads(response)
        return result.get('results', [])
    except json.JSONDecodeError:
        return []


async def _build_index(pdf_path: Path, ctx: Context, progress: Progress) -> dict:
    """内部函数：构建索引"""
    current_hash = get_pdf_hash(pdf_path)

    # 检查缓存
    cached = load_index(pdf_path)
    if cached and cached.get('file_hash') == current_hash:
        await ctx.info(f"使用缓存索引: {pdf_path.name}")
        return cached

    # 开始索引
    await ctx.info(f"开始索引 {pdf_path.name}...")

    total_pages = get_total_pages(pdf_path)
    progress.set_total(total_pages)
    pages_data = []

    for page_num in range(total_pages):
        progress.set_message(f"处理第 {page_num + 1}/{total_pages} 页")

        try:
            page_image = extract_page_as_image(pdf_path, page_num)
            image_b64 = image_to_base64(page_image)
            page_result = await ocr_and_summarize(image_b64, page_num + 1, ctx)
            pages_data.append(page_result)
        except Exception as e:
            await ctx.warning(f"第 {page_num + 1} 页处理失败: {e}")
            pages_data.append({
                "page": page_num + 1,
                "error": str(e),
                "text": "",
                "summary": "处理失败"
            })

        progress.increment()

    # 保存索引
    index_data = {
        "file_path": str(pdf_path),
        "file_hash": current_hash,
        "total_pages": total_pages,
        "indexed_at": datetime.now().isoformat(),
        "pages": pages_data
    }

    save_index(pdf_path, index_data)
    await ctx.info(f"索引完成: {pdf_path.name}, 共 {total_pages} 页")
    return index_data


@tool(task=True)
async def get_index(
    file_path: str,
    query: str | None = None,
    top_k: int = 5,
    ctx: Context = CurrentContext(),
    progress: Progress = Progress()
) -> dict:
    """
    获取 PDF 文件索引，支持语义搜索

    Args:
        file_path: PDF 文件的完整路径
        query: 搜索查询（可选）。如果提供，返回最相关的页面；否则返回全部索引
        top_k: 返回结果数量，默认 5（仅在有 query 时生效）
    """
    pdf_path = Path(file_path).expanduser().resolve()

    if not pdf_path.exists():
        return {"error": f"文件不存在: {file_path}"}

    # 获取或创建锁
    path_key = str(pdf_path)
    if path_key not in _indexing_locks:
        _indexing_locks[path_key] = Lock()

    # 使用锁防止并发索引同一文件
    async with _indexing_locks[path_key]:
        index_data = await _build_index(pdf_path, ctx, progress)

    # 如果有查询，执行 LLM 语义搜索
    if query:
        await ctx.info(f"搜索: {query}")
        search_results = await search_with_llm(query, index_data['pages'], ctx, top_k)

        return {
            "status": "search",
            "file_path": str(pdf_path),
            "query": query,
            "total_pages": index_data['total_pages'],
            "results": search_results
        }

    # 无查询，返回完整索引
    return {
        "status": "success",
        "file_path": str(pdf_path),
        "total_pages": index_data['total_pages'],
        "indexed_at": index_data['indexed_at'],
        "pages": index_data['pages']
    }
```

---

### 5️⃣ 详情工具（tools/detail.py）

```python
from fastmcp import tool
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext
from pathlib import Path

from shared.pdf_utils import load_index, get_index_path


@tool()
async def get_detail(
    file_path: str,
    page: int,
    ctx: Context = CurrentContext()
) -> dict:
    """
    获取 PDF 某一页的详细内容

    Args:
        file_path: PDF 文件的完整路径
        page: 页码（从 1 开始）
    """
    pdf_path = Path(file_path).expanduser().resolve()
    index_data = load_index(pdf_path)

    if not index_data:
        return {"error": f"未找到索引，请先运行: get_index('{file_path}')"}

    for page_data in index_data.get('pages', []):
        if page_data.get('page') == page:
            await ctx.debug(f"获取详情: {pdf_path.name} 第 {page} 页")
            return {
                "file_path": str(pdf_path),
                "page": page,
                "text": page_data.get('text', ''),
                "summary": page_data.get('summary', ''),
                "indexed_at": index_data.get('indexed_at')
            }

    return {
        "error": f"未找到第 {page} 页",
        "total_pages": index_data.get('total_pages', 0)
    }
```

---

## 🔥 进阶：自定义 Provider

如果需要更复杂的动态工具生成，可以创建自定义 Provider：

### providers/pdf_provider.py

```python
from fastmcp import Provider, Tool
from pathlib import Path


class PDFProvider(Provider):
    """
    自定义 Provider：可以动态生成工具或添加生命周期管理
    """

    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        super().__init__()

    def _list_tools(self) -> list[Tool]:
        """返回工具列表"""
        from tools.indexing import get_index
        from tools.detail import get_detail

        return [
            Tool.from_function(get_index),
            Tool.from_function(get_detail)
        ]

    @asynccontextmanager
    async def lifespan(self):
        """生命周期管理"""
        self.index_dir.mkdir(exist_ok=True)
        yield {"index_dir": self.index_dir}
```

### 使用自定义 Provider

```python
from fastmcp import FastMCP
from providers.pdf_provider import PDFProvider
from shared.config import INDEX_DIR

mcp = FastMCP("PDF索引助手")
mcp.add_provider(PDFProvider(INDEX_DIR))

if __name__ == "__main__":
    mcp.run()
```

---

## 📦 依赖安装

```bash
uv add fastmcp pymupdf pillow
```

✅ **无需系统依赖**，纯 Python 安装即可。

---

## 🖥️ Claude Desktop 配置

在 `~/Library/Application Support/Claude/claude_desktop_config.json` 添加：

**方式 A：stdio 模式（推荐）**
```json
{
  "mcpServers": {
    "pageindex": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/pageindex-light", "python", "server.py"]
    }
  }
}
```

**方式 B：SSE 模式（调试用）**
```json
{
  "mcpServers": {
    "pageindex": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

---

## 🆚 架构对比

| 特性 | 耦合版（旧） | Provider 架构（新） |
|------|-------------|-------------------|
| 主文件代码量 | ~150 行 | ~15 行 |
| 工具注册 | 手动 @mcp.tool | 自动发现 |
| 热重载 | ❌ | ✅ reload=True |
| 测试 | 需要启动服务器 | 可单独测试工具模块 |
| 扩展性 | 修改主文件 | 添加新文件即可 |

---

## 🚀 使用示例

```bash
# 启动
uv run python server.py
# 或
fastmcp run server.py:mcp
```

```
你: 帮我索引 ~/Documents/paper.pdf

Claude 调用: get_index("/Users/xxx/Documents/paper.pdf")

返回: {
  "status": "success",
  "file_path": "/Users/xxx/Documents/paper.pdf",
  "total_pages": 15,
  "pages": [...]
}
```

---

## 📊 v3 特性总结

| 特性 | 用途 |
|------|------|
| `FileSystemProvider` | 自动发现 tools/ 目录下的工具 |
| `reload=True` | 开发时热重载 |
| `Provider` 基类 | 自定义工具来源 |
| `Tool.from_function()` | 从函数创建工具 |
| `@tool(task=True)` | 后台异步任务 |
| `Progress` | 进度报告 |
| `CurrentContext()` | 依赖注入 |

---

✅ 主文件代码量：~15 行
✅ 工具数：2 个
✅ 解耦架构，易于扩展和测试
