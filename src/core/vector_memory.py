"""
Vector-based memory system using ChromaDB and Ollama embeddings

This module provides semantic memory capabilities using ChromaDB for vector storage
and Ollama's nomic-embed-text model for generating embeddings.
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import ollama

logger = logging.getLogger(__name__)

@dataclass
class VectorFact:
    """A fact stored in vector memory with metadata"""
    id: str
    content: str
    category: str
    timestamp: datetime
    relevance_score: float = 1.0
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata format"""
        return {
            'category': self.category,
            'timestamp': self.timestamp.isoformat(),
            'relevance_score': self.relevance_score
        }
    
    @classmethod
    def from_chromadb(cls, id: str, content: str, metadata: Dict[str, Any]) -> 'VectorFact':
        """Create VectorFact from ChromaDB result"""
        return cls(
            id=id,
            content=content,
            category=metadata.get('category', 'general'),
            timestamp=datetime.fromisoformat(metadata.get('timestamp', datetime.now().isoformat())),
            relevance_score=metadata.get('relevance_score', 1.0)
        )

class OllamaEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Custom embedding function using Ollama's nomic-embed-text model"""
    
    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        self._test_ollama_connection()
    
    def _test_ollama_connection(self):
        """Test if Ollama is running and model is available"""
        try:
            # Test with a simple embedding
            result = ollama.embed(model=self.model_name, input="test")
            if not result.get('embeddings'):
                raise ValueError(f"No embeddings returned from {self.model_name}")
            logger.info(f"Ollama embedding function initialized with {self.model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama embedding function: {e}")
            logger.warning(f"Vector search will not be available. Please ensure Ollama is running and run: ollama pull {self.model_name}")
            # Don't raise exception, allow graceful degradation
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        try:
            if not input:
                return []
            
            # Ollama embed expects a single string or list of strings
            if len(input) == 1:
                result = ollama.embed(model=self.model_name, input=input[0])
                return [result['embeddings'][0]]
            else:
                # For multiple inputs, call embed for each (Ollama handles batch internally)
                result = ollama.embed(model=self.model_name, input=input)
                return result['embeddings']
                
        except Exception as e:
            logger.error(f"Error generating embeddings with Ollama: {e}")
            # Return zero vectors as fallback to avoid breaking the system
            return [[0.0] * 768 for _ in input]  # nomic-embed-text has 768 dimensions

class VectorMemoryManager:
    """
    Hybrid memory manager using ChromaDB for semantic search and TinyDB for exact matches
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize vector memory manager"""
        self.cache_dir = cache_dir or self._get_cache_directory()
        self.chroma_path = os.path.join(self.cache_dir, 'chromadb')
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )
        
        # Initialize embedding function
        self.embedding_function = OllamaEmbeddingFunction()
        
        # Initialize collections
        self.facts_collection = self._get_or_create_collection("user_facts")
        self.conversations_collection = self._get_or_create_collection("conversations")
        
        # Import the original TinyDB memory manager for hybrid functionality
        from .memory import memory_manager as tiny_memory
        self.tiny_memory = tiny_memory
        
        logger.info(f"Vector memory manager initialized with ChromaDB at {self.chroma_path}")
    
    def _get_cache_directory(self) -> str:
        """Get memory cache directory"""
        cache_dir = os.path.expanduser('~/.cache/mcp_playground')
        try:
            os.makedirs(cache_dir, exist_ok=True)
            return cache_dir
        except (OSError, PermissionError):
            return os.path.join(os.path.expanduser('~'), '.mcp_playground')
    
    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        try:
            return self.client.get_collection(
                name=name,
                embedding_function=self.embedding_function
            )
        except (ValueError, Exception):
            # Collection doesn't exist, create it
            try:
                return self.client.create_collection(
                    name=name,
                    embedding_function=self.embedding_function,
                    metadata={"hnsw:space": "cosine"}  # Use cosine similarity
                )
            except Exception as e:
                logger.error(f"Failed to create collection {name}: {e}")
                # Create a dummy collection reference that will fail gracefully
                return None
    
    def store_fact(self, content: str, category: str = "general") -> str:
        """Store a fact in vector memory"""
        try:
            fact_id = f"fact_{datetime.now().timestamp()}"
            
            fact = VectorFact(
                id=fact_id,
                content=content,
                category=category,
                timestamp=datetime.now()
            )
            
            # Store in ChromaDB for semantic search (if available)
            if self.facts_collection is not None:
                self.facts_collection.add(
                    documents=[content],
                    metadatas=[fact.to_metadata()],
                    ids=[fact_id]
                )
                logger.info(f"Stored fact in vector memory: {fact_id}")
            else:
                logger.warning("ChromaDB collection not available, using TinyDB only")
            
            # Also store in TinyDB for backwards compatibility and exact matching
            self.tiny_memory.store_fact(content, category)
            
            return fact_id
            
        except Exception as e:
            logger.error(f"Failed to store fact in vector memory: {e}")
            # Fallback to TinyDB only
            return self.tiny_memory.store_fact(content, category)
    
    def retrieve_facts_semantic(self, query: str, limit: int = 5, min_similarity: float = 0.1) -> List[VectorFact]:
        """Retrieve facts using semantic similarity search"""
        try:
            if self.facts_collection is None:
                logger.warning("ChromaDB collection not available for semantic search")
                return []
            
            results = self.facts_collection.query(
                query_texts=[query],
                n_results=limit,
                include=['documents', 'metadatas', 'distances']
            )
            
            facts = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    # Convert distance to similarity (ChromaDB returns distances)
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    similarity = 1.0 - distance  # Convert cosine distance to similarity
                    
                    if similarity >= min_similarity:
                        fact = VectorFact.from_chromadb(
                            id=results['ids'][0][i],
                            content=doc,
                            metadata=results['metadatas'][0][i]
                        )
                        fact.relevance_score = similarity
                        facts.append(fact)
            
            logger.info(f"Semantic search for '{query}' returned {len(facts)} facts")
            return facts
            
        except Exception as e:
            logger.error(f"Error in semantic fact retrieval: {e}")
            # Fallback to TinyDB keyword search
            tiny_facts = self.tiny_memory.retrieve_facts(query, limit=limit)
            return [VectorFact(
                id=f"tiny_{i}",
                content=fact.content,
                category=fact.category,
                timestamp=fact.timestamp,
                relevance_score=0.5  # Default relevance for fallback
            ) for i, fact in enumerate(tiny_facts)]
    
    def retrieve_facts_hybrid(self, query: str, limit: int = 5) -> List[VectorFact]:
        """Retrieve facts using both semantic and keyword search, then merge results"""
        try:
            # Get semantic results
            semantic_facts = self.retrieve_facts_semantic(query, limit=limit)
            
            # Get keyword results from TinyDB as backup
            keyword_facts = self.tiny_memory.retrieve_facts(query, limit=limit)
            
            # Convert TinyDB facts to VectorFact format
            keyword_vector_facts = [VectorFact(
                id=f"keyword_{i}",
                content=fact.content,
                category=fact.category,
                timestamp=fact.timestamp,
                relevance_score=0.3  # Lower relevance for keyword matches
            ) for i, fact in enumerate(keyword_facts)]
            
            # Merge and deduplicate (prefer semantic matches)
            all_facts = semantic_facts + keyword_vector_facts
            seen_content = set()
            unique_facts = []
            
            for fact in all_facts:
                if fact.content not in seen_content:
                    seen_content.add(fact.content)
                    unique_facts.append(fact)
            
            # Sort by relevance score
            unique_facts.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return unique_facts[:limit]
            
        except Exception as e:
            logger.error(f"Error in hybrid fact retrieval: {e}")
            return []
    
    def forget_fact(self, fact_description: str) -> Tuple[bool, List[str]]:
        """Remove facts matching the description"""
        try:
            removed_items = []
            
            # Find matching facts using semantic search
            matching_facts = self.retrieve_facts_semantic(fact_description, limit=10, min_similarity=0.3)
            
            for fact in matching_facts:
                # Check if content is similar to what user wants to forget
                if any(word in fact.content.lower() for word in fact_description.lower().split()):
                    try:
                        # Remove from ChromaDB
                        self.facts_collection.delete(ids=[fact.id])
                        removed_items.append(fact.content[:50] + "..." if len(fact.content) > 50 else fact.content)
                        logger.info(f"Removed fact from vector memory: {fact.id}")
                    except Exception as e:
                        logger.warning(f"Failed to remove fact {fact.id} from ChromaDB: {e}")
            
            # Also try to remove from TinyDB
            try:
                tiny_removed = self.tiny_memory.forget_fact(fact_description)
                if tiny_removed and not removed_items:
                    removed_items.append("Legacy fact removed")
            except:
                pass
            
            return len(removed_items) > 0, removed_items
            
        except Exception as e:
            logger.error(f"Error forgetting facts: {e}")
            return False, []
    
    def get_all_facts(self) -> List[VectorFact]:
        """Get all stored facts from vector memory"""
        try:
            # Get all facts from ChromaDB
            results = self.facts_collection.get(include=['documents', 'metadatas'])
            
            facts = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    fact = VectorFact.from_chromadb(
                        id=results['ids'][i],
                        content=doc,
                        metadata=results['metadatas'][i]
                    )
                    facts.append(fact)
            
            return facts
            
        except Exception as e:
            logger.error(f"Error getting all facts: {e}")
            return []
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            stats = {
                'vector_facts_stored': self.facts_collection.count(),
                'chroma_path': self.chroma_path,
                'embedding_model': self.embedding_function.model_name,
                'cache_directory': self.cache_dir
            }
            
            # Add TinyDB stats for comparison
            tiny_stats = self.tiny_memory.get_memory_stats()
            stats.update({
                'tinydb_facts': tiny_stats.get('facts_stored', 0),
                'tinydb_conversations': tiny_stats.get('conversations_stored', 0),
                'tinydb_preferences': tiny_stats.get('preferences_stored', 0)
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {'error': str(e)}
    
    # Proxy methods to TinyDB for preferences and conversations
    def set_preference(self, key: str, value: Any) -> None:
        """Set user preference (uses TinyDB)"""
        return self.tiny_memory.set_preference(key, value)
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference (uses TinyDB)"""
        return self.tiny_memory.get_preference(key, default)
    
    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all user preferences (uses TinyDB)"""
        return self.tiny_memory.get_all_preferences()
    
    def save_conversation_summary(self, session_id: str, messages: List[Dict], tool_usage: Dict[str, int]) -> None:
        """Save conversation summary (uses TinyDB)"""
        return self.tiny_memory.save_conversation_summary(session_id, messages, tool_usage)
    
    def get_relevant_conversations(self, query: str, limit: int = 3) -> List:
        """Get relevant conversations (uses TinyDB for now, could be enhanced with vector search)"""
        return self.tiny_memory.get_relevant_conversations(query, limit)
    
    def build_conversation_context(self, current_query: str, session_history: List[Dict]) -> str:
        """Build context from memories for conversation with privacy protection"""
        # Use the enhanced privacy-aware context building from TinyDB memory manager
        return self.tiny_memory.build_conversation_context(current_query, session_history)
    

# Global vector memory manager instance
vector_memory_manager = VectorMemoryManager()