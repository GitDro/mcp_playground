"""
Unified SQLite-based caching system for all MCP tools

Provides consistent caching with smart TTL, related query optimization, and automatic cleanup.
"""

import os
import json
import sqlite3
import tempfile
import logging
from typing import Dict, Optional, Any, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache expiration strategies"""
    PERMANENT = "permanent"      # Never expires (e.g., YouTube transcripts, ArXiv papers)
    HOURLY = "hourly"           # 1 hour (e.g., weather, stock prices)
    DAILY = "daily"             # 24 hours (e.g., crime data, tides)
    WEEKLY = "weekly"           # 7 days (e.g., tide stations)
    CUSTOM = "custom"           # Custom TTL specified


@dataclass
class CacheConfig:
    """Configuration for different cache types"""
    tool_name: str
    data_type: str
    strategy: CacheStrategy
    custom_hours: Optional[int] = None
    max_entries: Optional[int] = None  # For size-based cleanup


# Default cache configurations for each tool
CACHE_CONFIGS = {
    # YouTube tool
    "youtube_transcript": CacheConfig("youtube", "transcript", CacheStrategy.PERMANENT),
    
    # Financial tools  
    "stock_current": CacheConfig("financial", "current", CacheStrategy.HOURLY),
    "stock_history": CacheConfig("financial", "history", CacheStrategy.DAILY),
    
    # Crime data
    "crime_data": CacheConfig("crime", "data", CacheStrategy.DAILY),
    "crime_neighbourhood": CacheConfig("crime", "neighbourhood", CacheStrategy.DAILY),
    
    # StatsCanada
    "statscan_cpi": CacheConfig("statscan", "cpi", CacheStrategy.DAILY),
    "statscan_gdp": CacheConfig("statscan", "gdp", CacheStrategy.CUSTOM, custom_hours=48),
    "statscan_employment": CacheConfig("statscan", "employment", CacheStrategy.CUSTOM, custom_hours=12),
    "statscan_overview": CacheConfig("statscan", "overview", CacheStrategy.CUSTOM, custom_hours=12),
    
    # Web tools
    "web_search": CacheConfig("web", "search", CacheStrategy.HOURLY),
    "web_content": CacheConfig("web", "content", CacheStrategy.DAILY),
    
    # Weather
    "weather_forecast": CacheConfig("weather", "forecast", CacheStrategy.HOURLY),
    "weather_location": CacheConfig("weather", "location", CacheStrategy.DAILY),
    
    # Tides
    "tides_stations": CacheConfig("tides", "stations", CacheStrategy.WEEKLY),
    "tides_predictions": CacheConfig("tides", "predictions", CacheStrategy.DAILY),
    
    # ArXiv
    "arxiv_paper": CacheConfig("arxiv", "paper", CacheStrategy.PERMANENT, max_entries=1000),
    "arxiv_search": CacheConfig("arxiv", "search", CacheStrategy.DAILY),
}


class UnifiedCache:
    """Unified SQLite-based cache manager for all MCP tools"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache manager"""
        self.cache_dir = cache_dir or self._get_cache_directory()
        self.db_path = os.path.join(self.cache_dir, 'unified_cache.db')
        self._init_database()
    
    def _get_cache_directory(self) -> str:
        """Get cache directory with fallback"""
        cache_dir = os.getenv('CACHE_DIRECTORY')
        if not cache_dir:
            cache_dir = os.path.expanduser('~/.cache/mcp_playground')
        
        try:
            os.makedirs(cache_dir, exist_ok=True)
            # Test writability
            test_file = os.path.join(cache_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return cache_dir
        except (OSError, PermissionError):
            return tempfile.gettempdir()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self) -> None:
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    metadata TEXT
                )
            ''')
            
            # Indexes for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tool_type ON cache_entries(tool_name, data_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created ON cache_entries(created_at)')
            
            conn.commit()
    
    def _calculate_expires_at(self, config: CacheConfig) -> Optional[str]:
        """Calculate expiration time based on cache strategy"""
        if config.strategy == CacheStrategy.PERMANENT:
            return None
        
        now = datetime.now()
        if config.strategy == CacheStrategy.HOURLY:
            expires = now + timedelta(hours=1)
        elif config.strategy == CacheStrategy.DAILY:
            expires = now + timedelta(days=1)
        elif config.strategy == CacheStrategy.WEEKLY:
            expires = now + timedelta(weeks=1)
        elif config.strategy == CacheStrategy.CUSTOM:
            if config.custom_hours:
                expires = now + timedelta(hours=config.custom_hours)
            else:
                expires = now + timedelta(hours=1)  # Default fallback
        else:
            expires = now + timedelta(hours=1)  # Default fallback
        
        return expires.isoformat()
    
    def get(self, cache_key: str, cache_type: str = "default") -> Optional[Dict]:
        """Get cached data by key"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT content, expires_at FROM cache_entries 
                    WHERE cache_key = ?
                ''', (cache_key,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Check expiration
                if row['expires_at']:
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if datetime.now() > expires_at:
                        # Expired - delete and return None
                        conn.execute('DELETE FROM cache_entries WHERE cache_key = ?', (cache_key,))
                        conn.commit()
                        return None
                
                return json.loads(row['content'])
                
        except Exception as e:
            logger.warning(f"Failed to get cached data for {cache_key}: {e}")
            return None
    
    def set(self, cache_key: str, data: Dict, cache_type: str = "default", 
            metadata: Optional[Dict] = None) -> None:
        """Set cached data with automatic TTL"""
        try:
            config = CACHE_CONFIGS.get(cache_type)
            if not config:
                # Default config for unknown types
                config = CacheConfig("unknown", "data", CacheStrategy.HOURLY)
            
            expires_at = self._calculate_expires_at(config)
            content_json = json.dumps(data)
            metadata_json = json.dumps(metadata) if metadata else None
            
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO cache_entries 
                    (cache_key, tool_name, data_type, content, created_at, expires_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cache_key,
                    config.tool_name,
                    config.data_type,
                    content_json,
                    datetime.now().isoformat(),
                    expires_at,
                    metadata_json
                ))
                
                # Cleanup old entries if there's a max_entries limit
                if config.max_entries:
                    conn.execute('''
                        DELETE FROM cache_entries 
                        WHERE tool_name = ? AND data_type = ? 
                        AND cache_key NOT IN (
                            SELECT cache_key FROM cache_entries 
                            WHERE tool_name = ? AND data_type = ?
                            ORDER BY created_at DESC 
                            LIMIT ?
                        )
                    ''', (config.tool_name, config.data_type, 
                          config.tool_name, config.data_type, config.max_entries))
                
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Failed to cache data for {cache_key}: {e}")
    
    def find_related(self, tool_name: str, data_type: str, search_term: str) -> List[Dict]:
        """Find related cached entries for smart query optimization"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT cache_key, content, metadata FROM cache_entries 
                    WHERE tool_name = ? AND data_type = ? 
                    AND (cache_key LIKE ? OR metadata LIKE ?)
                    AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY created_at DESC
                    LIMIT 10
                ''', (
                    tool_name, data_type, 
                    f'%{search_term}%', f'%{search_term}%',
                    datetime.now().isoformat()
                ))
                
                results = []
                for row in cursor.fetchall():
                    try:
                        results.append({
                            'cache_key': row['cache_key'],
                            'content': json.loads(row['content']),
                            'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                        })
                    except json.JSONDecodeError:
                        continue
                
                return results
                
        except Exception as e:
            logger.warning(f"Failed to find related entries: {e}")
            return []
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    DELETE FROM cache_entries 
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                ''', (datetime.now().isoformat(),))
                
                removed = cursor.rowcount
                conn.commit()
                
                if removed > 0:
                    logger.info(f"Cleaned up {removed} expired cache entries")
                
                return removed
                
        except Exception as e:
            logger.warning(f"Failed to cleanup expired entries: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with self._get_connection() as conn:
                # Total entries
                total = conn.execute('SELECT COUNT(*) FROM cache_entries').fetchone()[0]
                
                # By tool
                by_tool = {}
                cursor = conn.execute('''
                    SELECT tool_name, data_type, COUNT(*) as count 
                    FROM cache_entries 
                    GROUP BY tool_name, data_type
                ''')
                
                for row in cursor.fetchall():
                    tool = row['tool_name']
                    if tool not in by_tool:
                        by_tool[tool] = {}
                    by_tool[tool][row['data_type']] = row['count']
                
                # Database size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    'total_entries': total,
                    'by_tool': by_tool,
                    'database_size': db_size,
                    'cache_directory': self.cache_dir
                }
                
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {}
    
    def clear_tool_cache(self, tool_name: str) -> int:
        """Clear all cache entries for a specific tool"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'DELETE FROM cache_entries WHERE tool_name = ?', 
                    (tool_name,)
                )
                removed = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {removed} cache entries for tool: {tool_name}")
                return removed
                
        except Exception as e:
            logger.warning(f"Failed to clear cache for {tool_name}: {e}")
            return 0


# Global cache instance
cache = UnifiedCache()


# Convenience functions for backward compatibility
def get_cached_data(cache_key: str, cache_type: str = "default") -> Optional[Dict]:
    """Get cached data - backward compatible function"""
    return cache.get(cache_key, cache_type)


def save_cached_data(cache_key: str, data: Dict, cache_type: str = "default", 
                    metadata: Optional[Dict] = None) -> None:
    """Save data to cache - backward compatible function"""
    cache.set(cache_key, data, cache_type, metadata)


def cleanup_cache() -> int:
    """Clean up expired cache entries"""
    return cache.cleanup_expired()