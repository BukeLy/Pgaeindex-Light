from pathlib import Path
import fitz  # pymupdf
import hashlib
import json

from shared.config import INDEX_DIR


def get_pdf_hash(pdf_path: Path) -> str:
    """计算文件哈希"""
    with open(pdf_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get_index_path(pdf_path: Path) -> Path:
    """获取索引文件路径"""
    path_hash = hashlib.md5(str(pdf_path.absolute()).encode()).hexdigest()[:12]
    return INDEX_DIR / f"{pdf_path.stem}_{path_hash}.json"


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


def extract_page_text(pdf_path: Path, page_num: int) -> str:
    """提取 PDF 某页的文本内容（页码从 0 开始）"""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"页码 {page_num} 超出范围 [0, {len(doc) - 1}]")
        page = doc[page_num]
        return page.get_text()
    finally:
        if doc:
            doc.close()


def load_index(pdf_path: Path) -> dict | None:
    """加载索引"""
    index_path = get_index_path(pdf_path)
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_index(pdf_path: Path, index_data: dict):
    """保存索引"""
    index_path = get_index_path(pdf_path)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
