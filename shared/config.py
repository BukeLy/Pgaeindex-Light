from pathlib import Path
import os

INDEX_DIR = Path.home() / ".pageindex"
INDEX_DIR.mkdir(exist_ok=True)


# LLM 配置 (OpenAI 兼容 API)
LLM_BASE_URL = os.getenv("PAGEINDEX_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("PAGEINDEX_LLM_API_KEY", "")
LLM_MODEL = os.getenv("PAGEINDEX_LLM_MODEL", "gpt-4o-mini")

# OCR 配置
OCR_BASE_URL = os.getenv("PAGEINDEX_OCR_BASE_URL", "")
OCR_API_KEY = os.getenv("PAGEINDEX_OCR_API_KEY", "")
OCR_MODEL = os.getenv("PAGEINDEX_OCR_MODEL", "")


def is_llm_configured() -> bool:
    """检查 LLM 是否配置"""
    return bool(LLM_BASE_URL and LLM_API_KEY)


def is_ocr_configured() -> bool:
    """检查 OCR 是否配置"""
    return bool(OCR_BASE_URL and OCR_API_KEY and OCR_MODEL)
