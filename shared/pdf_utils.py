from pathlib import Path
import fitz  # pymupdf
import hashlib
import json
import base64
import os

from shared.config import INDEX_DIR


def get_ocr_config():
    return (
        os.environ.get("PAGEINDEX_OCR_BASE_URL", ""),
        os.environ.get("PAGEINDEX_OCR_API_KEY", ""),
        os.environ.get("PAGEINDEX_OCR_MODEL", ""),
    )


def is_ocr_configured():
    base_url, api_key, model = get_ocr_config()
    return bool(base_url and api_key and model)


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


async def ocr_page_image(pdf_path: Path, page_num: int) -> str:
    """使用 OCR 提取 PDF 某页的文本内容（页码从 0 开始）

    Returns:
        提取的文本内容，OCR 失败时返回空字符串
    """
    import openai

    doc = None
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"页码 {page_num} 超出范围 [0, {len(doc) - 1}]")

        page = doc[page_num]
        # 渲染页面为图片 (2x 缩放提高清晰度)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        try:
            base_url, api_key, model = get_ocr_config()
            client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_base64}"}
                            },
                            {
                                "type": "text",
                                "text": "请提取图片中的所有文字内容，保持原有格式和布局。只输出文字内容，不要添加任何解释。"
                            }
                        ]
                    }
                ]
            )
            return response.choices[0].message.content or ""
        except openai.APIConnectionError as e:
            raise RuntimeError(f"OCR 服务连接失败: {e}") from e
        except openai.RateLimitError as e:
            raise RuntimeError(f"OCR 服务请求频率超限: {e}") from e
        except openai.APIStatusError as e:
            raise RuntimeError(f"OCR 服务返回错误 (状态码 {e.status_code}): {e.message}") from e
        except Exception as e:
            # 其他未知异常，返回空字符串并记录
            return ""
    finally:
        if doc:
            doc.close()


async def extract_page_text(pdf_path: Path, page_num: int) -> str:
    """提取 PDF 某页的文本内容（页码从 0 开始）

    如果 pymupdf 提取的文本为空或过短，且 OCR 已配置，则使用 OCR 提取
    """
    doc = None
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"页码 {page_num} 超出范围 [0, {len(doc) - 1}]")
        page = doc[page_num]
        text = page.get_text()

        # 如果文本为空或过短，尝试使用 OCR
        if len(text.strip()) < 10 and is_ocr_configured():
            doc.close()
            doc = None
            text = await ocr_page_image(pdf_path, page_num)

        return text
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
