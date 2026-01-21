from pathlib import Path
import os

INDEX_DIR = Path.home() / ".pageindex"
INDEX_DIR.mkdir(exist_ok=True)


def get_llm_config() -> tuple[str, str, str]:
    """获取 LLM 配置 (动态读取环境变量)"""
    return (
        os.getenv("PAGEINDEX_LLM_BASE_URL", ""),
        os.getenv("PAGEINDEX_LLM_API_KEY", ""),
        os.getenv("PAGEINDEX_LLM_MODEL", "gpt-4o-mini"),
    )


def get_ocr_config() -> tuple[str, str, str]:
    """获取 OCR 配置 (动态读取环境变量)"""
    return (
        os.getenv("PAGEINDEX_OCR_BASE_URL", ""),
        os.getenv("PAGEINDEX_OCR_API_KEY", ""),
        os.getenv("PAGEINDEX_OCR_MODEL", ""),
    )


def is_llm_configured() -> bool:
    """检查 LLM 是否配置"""
    base_url, api_key, _ = get_llm_config()
    return bool(base_url and api_key)


def is_ocr_configured() -> bool:
    """检查 OCR 是否配置"""
    base_url, api_key, model = get_ocr_config()
    return bool(base_url and api_key and model)
