"""
State management integration for retry system using existing vector memory.

Provides persistent storage and learning capabilities for retry contexts,
enabling the system to improve over time by learning from successful corrections.
"""

import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from .vector_memory import VectorMemoryManager, VectorFact
from .retry_manager import RetryContext, ErrorType, RetryAttempt

logger = logging.getLogger(__name__)


@dataclass
class RetryPattern:
    """A pattern learned from successful retry attempts"""
    tool_name: str
    error_type: str
    original_args: Dict[str, Any]
    corrected_args: Dict[str, Any]
    success_count: int = 1
    last_used: datetime = None
    confidence_score: float = 1.0
    
    def __post_init__(self):
        if self.last_used is None:
            self.last_used = datetime.now()
    
    def to_storage_format(self) -> Dict[str, Any]:
        """Convert to format suitable for vector storage"""
        return {
            'tool_name': self.tool_name,
            'error_type': self.error_type,
            'original_args': json.dumps(self.original_args, sort_keys=True),
            'corrected_args': json.dumps(self.corrected_args, sort_keys=True),
            'success_count': self.success_count,
            'last_used': self.last_used.isoformat(),
            'confidence_score': self.confidence_score
        }
    
    @classmethod
    def from_storage_format(cls, data: Dict[str, Any]) -> 'RetryPattern':
        """Create from stored data"""
        return cls(
            tool_name=data['tool_name'],
            error_type=data['error_type'],
            original_args=json.loads(data['original_args']),
            corrected_args=json.loads(data['corrected_args']),
            success_count=data.get('success_count', 1),
            last_used=datetime.fromisoformat(data.get('last_used', datetime.now().isoformat())),
            confidence_score=data.get('confidence_score', 1.0)
        )
    
    def get_search_text(self) -> str:
        """Generate text for semantic search"""
        args_desc = ", ".join(f"{k}={v}" for k, v in self.original_args.items())
        return f"Tool {self.tool_name} {self.error_type} error with args: {args_desc}"


class RetryStateManager:
    """Manages persistent state for retry contexts using vector memory"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.vector_memory = VectorMemoryManager(cache_dir)
        
        # Create dedicated collection for retry patterns
        self.retry_collection = self.vector_memory._get_or_create_collection("retry_patterns")
        
        # Cache for frequently used patterns
        self._pattern_cache: Dict[str, RetryPattern] = {}
        self._cache_ttl = timedelta(hours=1)
        self._last_cache_cleanup = datetime.now()
        
        logger.info("Retry state manager initialized with vector memory backend")
    
    def record_successful_retry(self, context: RetryContext) -> None:
        """Record a successful retry for future learning"""
        if not context.corrected_args or context.attempt_count <= 1:
            return  # Nothing to learn from
        
        # Find the successful attempt
        successful_attempt = None
        for attempt in context.attempts:
            if attempt.success:
                successful_attempt = attempt
                break
        
        if not successful_attempt:
            return
        
        # Create or update retry pattern
        pattern = RetryPattern(
            tool_name=context.tool_name,
            error_type=successful_attempt.error_type.value,
            original_args=context.original_args,
            corrected_args=context.corrected_args
        )
        
        # Check if similar pattern exists
        existing_pattern = self._find_similar_pattern(pattern)
        if existing_pattern:
            # Update existing pattern
            existing_pattern.success_count += 1
            existing_pattern.last_used = datetime.now()
            existing_pattern.confidence_score = min(1.0, existing_pattern.confidence_score + 0.1)
            self._update_pattern(existing_pattern)
            logger.info(f"Updated retry pattern for {context.tool_name}: success_count={existing_pattern.success_count}")
        else:
            # Store new pattern
            self._store_pattern(pattern)
            logger.info(f"Stored new retry pattern for {context.tool_name}")
    
    def predict_correction(self, tool_name: str, args: Dict[str, Any], error_type: ErrorType) -> Optional[Dict[str, Any]]:
        """Predict argument corrections based on learned patterns"""
        # Clean cache periodically
        self._cleanup_cache_if_needed()
        
        # Search for similar patterns
        search_text = f"Tool {tool_name} {error_type.value} error"
        patterns = self._search_patterns(search_text, limit=5)
        
        # Filter by tool name and error type
        matching_patterns = [
            p for p in patterns 
            if p.tool_name == tool_name and p.error_type == error_type.value
        ]
        
        if not matching_patterns:
            return None
        
        # Find best matching pattern based on argument similarity
        best_pattern = self._find_best_matching_pattern(matching_patterns, args)
        
        if best_pattern and best_pattern.confidence_score > 0.5:
            logger.info(f"Predicted correction for {tool_name} based on pattern with confidence {best_pattern.confidence_score}")
            return best_pattern.corrected_args
        
        return None
    
    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about stored retry patterns"""
        try:
            # Get all patterns
            results = self.retry_collection.get()
            total_patterns = len(results['ids']) if results['ids'] else 0
            
            # Parse patterns for analysis
            patterns = []
            if results['metadatas']:
                for i, metadata in enumerate(results['metadatas']):
                    try:
                        pattern_data = json.loads(results['documents'][i])
                        patterns.append(RetryPattern.from_storage_format(pattern_data))
                    except (json.JSONDecodeError, KeyError):
                        continue
            
            # Calculate statistics
            tool_counts = {}
            error_type_counts = {}
            total_successes = 0
            
            for pattern in patterns:
                tool_counts[pattern.tool_name] = tool_counts.get(pattern.tool_name, 0) + 1
                error_type_counts[pattern.error_type] = error_type_counts.get(pattern.error_type, 0) + 1
                total_successes += pattern.success_count
            
            return {
                "total_patterns": total_patterns,
                "total_successes": total_successes,
                "tools_with_patterns": len(tool_counts),
                "most_common_tools": sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5],
                "most_common_errors": sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True)[:5],
                "cache_size": len(self._pattern_cache)
            }
        except Exception as e:
            logger.error(f"Error calculating pattern stats: {e}")
            return {"error": str(e)}
    
    def cleanup_old_patterns(self, days: int = 30) -> int:
        """Remove patterns older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        try:
            results = self.retry_collection.get()
            if not results['ids']:
                return 0
            
            ids_to_remove = []
            for i, doc in enumerate(results['documents']):
                try:
                    pattern_data = json.loads(doc)
                    pattern = RetryPattern.from_storage_format(pattern_data)
                    if pattern.last_used < cutoff_date:
                        ids_to_remove.append(results['ids'][i])
                        removed_count += 1
                except (json.JSONDecodeError, KeyError):
                    continue
            
            if ids_to_remove:
                self.retry_collection.delete(ids=ids_to_remove)
                logger.info(f"Cleaned up {removed_count} old retry patterns")
            
        except Exception as e:
            logger.error(f"Error cleaning up old patterns: {e}")
        
        return removed_count
    
    def _store_pattern(self, pattern: RetryPattern) -> None:
        """Store a retry pattern in vector memory"""
        pattern_id = self._generate_pattern_id(pattern)
        search_text = pattern.get_search_text()
        storage_data = json.dumps(pattern.to_storage_format())
        
        try:
            self.retry_collection.upsert(
                ids=[pattern_id],
                documents=[storage_data],
                metadatas=[{
                    'tool_name': pattern.tool_name,
                    'error_type': pattern.error_type,
                    'timestamp': pattern.last_used.isoformat(),
                    'confidence_score': pattern.confidence_score
                }]
            )
            
            # Add to cache
            self._pattern_cache[pattern_id] = pattern
            
        except Exception as e:
            logger.error(f"Error storing retry pattern: {e}")
    
    def _update_pattern(self, pattern: RetryPattern) -> None:
        """Update an existing pattern"""
        pattern_id = self._generate_pattern_id(pattern)
        self._store_pattern(pattern)  # Upsert handles updates
    
    def _find_similar_pattern(self, pattern: RetryPattern) -> Optional[RetryPattern]:
        """Find a similar existing pattern"""
        pattern_id = self._generate_pattern_id(pattern)
        
        # Check cache first
        if pattern_id in self._pattern_cache:
            return self._pattern_cache[pattern_id]
        
        # Search in storage
        try:
            results = self.retry_collection.get(ids=[pattern_id])
            if results['ids'] and results['documents']:
                pattern_data = json.loads(results['documents'][0])
                existing_pattern = RetryPattern.from_storage_format(pattern_data)
                self._pattern_cache[pattern_id] = existing_pattern
                return existing_pattern
        except Exception as e:
            logger.debug(f"Pattern not found in storage: {e}")
        
        return None
    
    def _search_patterns(self, query: str, limit: int = 10) -> List[RetryPattern]:
        """Search for patterns using semantic similarity"""
        try:
            results = self.retry_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            patterns = []
            if results['documents'] and results['documents'][0]:
                for doc in results['documents'][0]:
                    try:
                        pattern_data = json.loads(doc)
                        pattern = RetryPattern.from_storage_format(pattern_data)
                        patterns.append(pattern)
                    except (json.JSONDecodeError, KeyError):
                        continue
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error searching patterns: {e}")
            return []
    
    def _find_best_matching_pattern(self, patterns: List[RetryPattern], args: Dict[str, Any]) -> Optional[RetryPattern]:
        """Find the pattern that best matches the given arguments"""
        best_pattern = None
        best_score = 0.0
        
        for pattern in patterns:
            # Calculate similarity score based on argument overlap
            score = self._calculate_argument_similarity(pattern.original_args, args)
            # Weight by confidence and success count
            weighted_score = score * pattern.confidence_score * min(1.0, pattern.success_count / 5.0)
            
            if weighted_score > best_score:
                best_score = weighted_score
                best_pattern = pattern
        
        return best_pattern if best_score > 0.3 else None
    
    def _calculate_argument_similarity(self, args1: Dict[str, Any], args2: Dict[str, Any]) -> float:
        """Calculate similarity between two argument dictionaries"""
        if not args1 or not args2:
            return 0.0
        
        # Check key overlap
        keys1 = set(args1.keys())
        keys2 = set(args2.keys())
        key_overlap = len(keys1 & keys2) / len(keys1 | keys2)
        
        # Check value similarity for overlapping keys
        value_matches = 0
        total_overlapping = len(keys1 & keys2)
        
        if total_overlapping > 0:
            for key in keys1 & keys2:
                if args1[key] == args2[key]:
                    value_matches += 1
                elif isinstance(args1[key], str) and isinstance(args2[key], str):
                    # Partial string similarity
                    if args1[key].lower() in args2[key].lower() or args2[key].lower() in args1[key].lower():
                        value_matches += 0.5
            
            value_similarity = value_matches / total_overlapping
        else:
            value_similarity = 0.0
        
        # Combine key and value similarity
        return (key_overlap + value_similarity) / 2.0
    
    def _generate_pattern_id(self, pattern: RetryPattern) -> str:
        """Generate a consistent ID for a retry pattern"""
        # Create hash based on tool name, error type, and argument structure
        key_parts = [
            pattern.tool_name,
            pattern.error_type,
            json.dumps(sorted(pattern.original_args.keys())),
            json.dumps(pattern.original_args, sort_keys=True)
        ]
        key_string = "|".join(str(part) for part in key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _cleanup_cache_if_needed(self) -> None:
        """Clean up expired cache entries"""
        now = datetime.now()
        if now - self._last_cache_cleanup > self._cache_ttl:
            expired_keys = [
                key for key, pattern in self._pattern_cache.items()
                if now - pattern.last_used > self._cache_ttl
            ]
            for key in expired_keys:
                del self._pattern_cache[key]
            
            self._last_cache_cleanup = now
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


# Global instance for easy access
_retry_state_manager = None

def get_retry_state_manager() -> RetryStateManager:
    """Get the global retry state manager instance"""
    global _retry_state_manager
    if _retry_state_manager is None:
        _retry_state_manager = RetryStateManager()
    return _retry_state_manager