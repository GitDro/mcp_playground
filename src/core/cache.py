"""
DEPRECATED: Legacy caching utilities - use unified_cache.py instead

This file is maintained for backward compatibility only.
All new caching should use the unified SQLite-based system.
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, Optional
from .unified_cache import get_cached_data, save_cached_data as save_unified_data, cleanup_cache

logger = logging.getLogger(__name__)

# Backward compatibility functions - redirect to unified cache
def load_cached_data(cache_key: str) -> Optional[Dict]:
    """DEPRECATED: Use unified_cache.get_cached_data instead"""
    logger.warning("load_cached_data is deprecated, use unified_cache.get_cached_data")
    return get_cached_data(cache_key, "default")


def save_cached_data(cache_key: str, data: Dict) -> None:
    """DEPRECATED: Use unified_cache.save_cached_data instead"""
    logger.warning("save_cached_data is deprecated, use unified_cache.save_cached_data")
    save_unified_data(cache_key, data, "default")


def cleanup_old_cache() -> None:
    """DEPRECATED: Use unified_cache.cleanup_cache instead"""
    logger.warning("cleanup_old_cache is deprecated, use unified_cache.cleanup_cache")
    cleanup_cache()


# All transcript caching functionality has been moved to unified_cache.py
# YouTube tools now use the unified caching system with proper table schemas