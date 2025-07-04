"""
Caching utilities for MCP tools
"""

import os
import json
import tempfile
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _get_cache_directory() -> str:
    """Get writable cache directory, falling back to temp if needed"""
    cache_dir = os.getenv('CACHE_DIRECTORY')
    if not cache_dir:
        # Try user cache directory first
        cache_dir = os.path.expanduser('~/.cache/mcp_playground')
    
    try:
        os.makedirs(cache_dir, exist_ok=True)
        # Test if directory is writable
        test_file = os.path.join(cache_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return cache_dir
    except (OSError, PermissionError):
        # Fallback to temp directory
        return tempfile.gettempdir()


CACHE_DIR = _get_cache_directory()
MAX_CACHE_DAYS = int(os.getenv('MAX_CACHE_DAYS', '7'))


def _get_cache_file_path(ticker: str, date_str: str = None) -> str:
    """Get the cache file path for a ticker on a specific date"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    cache_date_dir = os.path.join(CACHE_DIR, date_str)
    os.makedirs(cache_date_dir, exist_ok=True)
    return os.path.join(cache_date_dir, f"{ticker.upper()}.json")


def load_cached_data(ticker: str) -> Optional[Dict]:
    """Load cached stock data for today if it exists"""
    try:
        cache_file = _get_cache_file_path(ticker)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)
                # Check if data is from today
                if data.get('date') == datetime.now().strftime('%Y-%m-%d'):
                    return data
        return None
    except Exception:
        return None


def save_cached_data(ticker: str, data: Dict) -> None:
    """Save stock data to cache"""
    try:
        data['date'] = datetime.now().strftime('%Y-%m-%d')
        data['cached_at'] = datetime.now().isoformat()
        
        cache_file = _get_cache_file_path(ticker)
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to cache data for {ticker}: {e}")


def cleanup_old_cache() -> None:
    """Remove cache directories older than MAX_CACHE_DAYS"""
    try:
        if not os.path.exists(CACHE_DIR):
            return
            
        cutoff_date = datetime.now() - timedelta(days=MAX_CACHE_DAYS)
        
        for item in os.listdir(CACHE_DIR):
            item_path = os.path.join(CACHE_DIR, item)
            if os.path.isdir(item_path):
                try:
                    # Check if directory name is a date
                    dir_date = datetime.strptime(item, '%Y-%m-%d')
                    if dir_date < cutoff_date:
                        import shutil
                        shutil.rmtree(item_path)
                        logger.info(f"Cleaned up old cache directory: {item}")
                except ValueError:
                    # Not a date directory, skip
                    continue
    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")


def get_transcript_db():
    """Get or create TinyDB database for transcripts"""
    from tinydb import TinyDB
    
    # Use user's cache directory or temp directory if read-only
    cache_dir = os.path.expanduser('~/.cache/mcp_playground')
    try:
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, 'transcripts.json')
    except (OSError, PermissionError):
        # Fallback to temp directory if cache dir is not writable
        db_path = os.path.join(tempfile.gettempdir(), 'mcp_playground_transcripts.json')
    
    return TinyDB(db_path)