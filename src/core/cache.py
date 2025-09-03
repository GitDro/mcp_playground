"""
DEPRECATED: Legacy caching utilities - use unified_cache.py instead

This file is maintained for backward compatibility only.
All new caching should use the unified SQLite-based system.
"""

import logging
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


def get_transcript_db():
    """Get or create SQLite database for transcripts"""
    import sqlite3
    
    # Use user's cache directory or temp directory if read-only
    cache_dir = os.path.expanduser('~/.cache/mcp_playground')
    try:
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, 'transcripts.db')
    except (OSError, PermissionError):
        # Fallback to temp directory if cache dir is not writable
        db_path = os.path.join(tempfile.gettempdir(), 'mcp_playground_transcripts.db')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    
    # Create table if it doesn't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transcripts (
            video_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            transcript TEXT NOT NULL,
            created_at TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en'
        )
    ''')
    conn.commit()
    
    return conn


def get_cached_transcript(video_id: str) -> Optional[Dict]:
    """Get cached transcript by video ID"""
    try:
        with get_transcript_db() as conn:
            cursor = conn.execute(
                'SELECT * FROM transcripts WHERE video_id = ?',
                (video_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Failed to get cached transcript for {video_id}: {e}")
        return None


def save_transcript_cache(video_id: str, url: str, title: str, transcript: str, language: str = 'en') -> None:
    """Save transcript to cache"""
    try:
        with get_transcript_db() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO transcripts 
                (video_id, url, title, transcript, created_at, language)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (video_id, url, title, transcript, datetime.now().isoformat(), language))
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to cache transcript for {video_id}: {e}")