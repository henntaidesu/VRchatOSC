"""
多语言支持模块
"""

from .language_dict import (
    LANGUAGE_TEXTS,
    LANGUAGE_DISPLAY_MAP,
    DISPLAY_TO_LANGUAGE_MAP,
    get_text,
    get_available_languages,
    get_language_display_names
)

__all__ = [
    'LANGUAGE_TEXTS',
    'LANGUAGE_DISPLAY_MAP', 
    'DISPLAY_TO_LANGUAGE_MAP',
    'get_text',
    'get_available_languages',
    'get_language_display_names'
]