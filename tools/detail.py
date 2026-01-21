from fastmcp import Context
from fastmcp.tools import tool
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.pdf_utils import load_index


@tool()
async def get_detail(
    file_path: str,
    page: int,
    ctx: Context = None,
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

    for page_data in index_data.get("pages", []):
        if page_data.get("page") == page:
            if ctx:
                await ctx.debug(f"获取详情: {pdf_path.name} 第 {page} 页")
            return {
                "file_path": str(pdf_path),
                "page": page,
                "text": page_data.get("text", ""),
                "summary": page_data.get("summary", ""),
                "indexed_at": index_data.get("indexed_at"),
            }

    return {"error": f"未找到第 {page} 页", "total_pages": index_data.get("total_pages", 0)}
