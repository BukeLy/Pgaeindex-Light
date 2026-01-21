from fastmcp import Context
from fastmcp.tools import tool
from pathlib import Path
from datetime import datetime
from asyncio import Lock
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.pdf_utils import (
    get_pdf_hash,
    extract_page_text,
    load_index,
    save_index,
    get_total_pages,
)

# 并发锁：防止同一文件被重复索引
_indexing_locks: dict[str, Lock] = {}


async def summarize_text(text: str, page_num: int, ctx: Context) -> dict:
    """用 LLM 总结页面内容"""
    if not text.strip():
        return {"page": page_num, "text": "", "summary": "空白页"}

    # 截断过长文本
    truncated = text[:3000] if len(text) > 3000 else text

    response = await ctx.sample(
        f"""请用1-2句话总结以下第{page_num}页的内容：

{truncated}

仅返回摘要文本，不要添加任何前缀或解释。"""
    )

    return {"page": page_num, "text": text, "summary": response.text.strip()}


async def search_with_llm(
    query: str, pages: list[dict], ctx: Context, top_k: int = 5
) -> list[dict]:
    """用 LLM 对索引进行语义搜索"""
    summaries = "\n".join(
        [
            f"第{p['page']}页: {p.get('summary', '无摘要')}"
            for p in pages
            if not p.get("error")
        ]
    )

    response = await ctx.sample(
        f"""根据用户查询，从以下页面摘要中找出最相关的页面。

用户查询: {query}

页面摘要列表:
{summaries}

请返回最相关的页码（最多{top_k}个），按相关性排序。
返回JSON格式：{{"results": [{{"page": 页码, "relevance": "相关原因"}}]}}
仅返回JSON，不要其他内容。"""
    )

    try:
        result = json.loads(response.text)
        return result.get("results", [])
    except json.JSONDecodeError:
        return []


async def _build_index(pdf_path: Path, ctx: Context) -> dict:
    """内部函数：构建索引"""
    current_hash = get_pdf_hash(pdf_path)

    # 检查缓存
    cached = load_index(pdf_path)
    if cached and cached.get("file_hash") == current_hash:
        await ctx.info(f"使用缓存索引: {pdf_path.name}")
        return cached

    # 开始索引
    await ctx.info(f"开始索引 {pdf_path.name}...")

    total_pages = get_total_pages(pdf_path)
    pages_data = []

    for page_num in range(total_pages):
        await ctx.report_progress(progress=page_num, total=total_pages)

        try:
            page_text = extract_page_text(pdf_path, page_num)
            page_result = await summarize_text(page_text, page_num + 1, ctx)
            pages_data.append(page_result)
        except Exception as e:
            await ctx.warning(f"第 {page_num + 1} 页处理失败: {e}")
            pages_data.append(
                {
                    "page": page_num + 1,
                    "error": str(e),
                    "text": "",
                    "summary": "处理失败",
                }
            )

    await ctx.report_progress(progress=total_pages, total=total_pages)

    # 保存索引
    index_data = {
        "file_path": str(pdf_path),
        "file_hash": current_hash,
        "total_pages": total_pages,
        "indexed_at": datetime.now().isoformat(),
        "pages": pages_data,
    }

    save_index(pdf_path, index_data)
    await ctx.info(f"索引完成: {pdf_path.name}, 共 {total_pages} 页")
    return index_data


@tool()
async def get_index(
    file_path: str,
    query: str | None = None,
    top_k: int = 5,
    ctx: Context = None,
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

    if not pdf_path.suffix.lower() == ".pdf":
        return {"error": f"不是 PDF 文件: {file_path}"}

    # 获取或创建锁
    path_key = str(pdf_path)
    if path_key not in _indexing_locks:
        _indexing_locks[path_key] = Lock()

    # 使用锁防止并发索引同一文件
    async with _indexing_locks[path_key]:
        index_data = await _build_index(pdf_path, ctx)

    # 如果有查询，执行 LLM 语义搜索
    if query:
        await ctx.info(f"搜索: {query}")
        search_results = await search_with_llm(query, index_data["pages"], ctx, top_k)

        return {
            "status": "search",
            "file_path": str(pdf_path),
            "query": query,
            "total_pages": index_data["total_pages"],
            "results": search_results,
        }

    # 无查询，返回完整索引（仅摘要）
    return {
        "status": "success",
        "file_path": str(pdf_path),
        "total_pages": index_data["total_pages"],
        "indexed_at": index_data["indexed_at"],
        "pages": [
            {"page": p["page"], "summary": p.get("summary", "")}
            for p in index_data["pages"]
        ],
    }
