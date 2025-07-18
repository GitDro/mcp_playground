"""
Vector-based memory system using ChromaDB and Ollama embeddings

This module provides semantic memory capabilities using ChromaDB for vector storage
and Ollama's nomic-embed-text model for generating embeddings.
"""

import os
import logging
import uuid
import hashlib
import threading
import time
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
    
    def name(self) -> str:
        """Return the name of this embedding function (required by ChromaDB)"""
        return f"ollama-{self.model_name}"
    
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
        self.documents_collection = self._get_or_create_collection("documents")
        
        # Import the original TinyDB memory manager for hybrid functionality
        from .memory import memory_manager as tiny_memory
        self.tiny_memory = tiny_memory
        
        # Initialize file watching for documents
        self.documents_dir = os.path.join(self.cache_dir, 'documents')
        self._file_timestamps = {}
        self._watcher_thread = None
        self._watcher_running = False
        self._start_file_watcher()
        
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
    
    # Document Management Methods
    def store_document(self, title: str, content: str, doc_type: str = "note", 
                      tags: List[str] = None, file_path: str = None, 
                      source_url: str = None, summary: str = None) -> str:
        """Store a document in vector memory and optionally as a file"""
        try:
            from .models import Document
            
            # Generate meaningful document ID
            def create_document_id(title: str, doc_type: str, source_url: str = None) -> str:
                # Create a slug from title
                title_slug = "".join(c.lower() if c.isalnum() else "_" for c in title)[:30]
                title_slug = title_slug.strip("_")
                
                # Add type prefix
                if source_url:
                    # For URLs, use domain
                    from urllib.parse import urlparse
                    try:
                        domain = urlparse(source_url).netloc.replace("www.", "").replace(".", "_")[:15]
                        prefix = f"url_{domain}"
                    except:
                        prefix = "url"
                elif doc_type == "note":
                    prefix = "note"
                elif doc_type == "capture":
                    prefix = "capture"
                else:
                    prefix = doc_type
                
                # Add date
                date_str = datetime.now().strftime("%m%d")
                
                # Combine
                base_id = f"{prefix}_{title_slug}_{date_str}"
                
                # Ensure uniqueness with short hash if needed
                content_hash = hashlib.md5(f"{title}{content}".encode()).hexdigest()[:4]
                return f"{base_id}_{content_hash}"
            
            # Check for URL deduplication
            if source_url:
                existing_docs = self.get_all_documents()
                for existing_doc in existing_docs:
                    if existing_doc.get('source_url') == source_url:
                        logger.info(f"Document with URL {source_url} already exists: {existing_doc['id']}")
                        return existing_doc['id']  # Return existing document ID
            
            doc_id = create_document_id(title, doc_type, source_url)
            
            # Create document model
            document = Document(
                id=doc_id,
                title=title,
                content=content,
                summary=summary,
                tags=tags or [],
                doc_type=doc_type,
                file_path=file_path,
                source_url=source_url
            )
            
            # Store in ChromaDB for semantic search
            if self.documents_collection is not None:
                # For long documents, we might want to chunk them
                # For now, store the full content with metadata
                self.documents_collection.add(
                    documents=[content],
                    metadatas=[document.to_chromadb_metadata()],
                    ids=[doc_id]
                )
                logger.info(f"Stored document in vector memory: {doc_id}")
            else:
                logger.warning("ChromaDB documents collection not available")
            
            # Optionally save as file
            if file_path:
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        # Write markdown with frontmatter
                        f.write(f"---\n")
                        f.write(f"title: {title}\n")
                        f.write(f"doc_type: {doc_type}\n")
                        f.write(f"tags: [{', '.join(tags or [])}]\n")
                        if source_url:
                            f.write(f"source_url: {source_url}\n")
                        f.write(f"created_at: {document.created_at.isoformat()}\n")
                        f.write(f"---\n\n")
                        f.write(content)
                    logger.info(f"Saved document to file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to save document to file {file_path}: {e}")
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            raise
    
    def search_documents(self, query: str, limit: int = 5, min_similarity: float = 0.1, 
                        doc_type: str = None, tags: List[str] = None) -> List[Dict[str, Any]]:
        """Search documents using semantic similarity"""
        try:
            if self.documents_collection is None:
                logger.warning("ChromaDB documents collection not available for search")
                return []
            
            # Build where clause for filtering
            where_clause = {}
            if doc_type:
                where_clause["doc_type"] = doc_type
            
            # Perform semantic search
            search_params = {
                "query_texts": [query],
                "n_results": limit,
                "include": ['documents', 'metadatas', 'distances']
            }
            
            if where_clause:
                search_params["where"] = where_clause
            
            results = self.documents_collection.query(**search_params)
            
            documents = []
            if results['documents'] and results['documents'][0]:
                for i, doc_content in enumerate(results['documents'][0]):
                    # Convert distance to similarity
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    similarity = 1.0 - distance
                    
                    if similarity >= min_similarity:
                        metadata = results['metadatas'][0][i]
                        
                        # Filter by tags if specified
                        if tags:
                            doc_tags = metadata.get('tags', '').split(',') if metadata.get('tags') else []
                            if not any(tag.strip() in doc_tags for tag in tags):
                                continue
                        
                        # Create search result
                        doc_result = {
                            'id': results['ids'][0][i],
                            'title': metadata.get('title', 'Untitled'),
                            'content': doc_content,
                            'doc_type': metadata.get('doc_type', 'note'),
                            'tags': metadata.get('tags', '').split(',') if metadata.get('tags') else [],
                            'source_url': metadata.get('source_url') or None,
                            'file_path': metadata.get('file_path') or None,
                            'created_at': metadata.get('created_at'),
                            'relevance_score': similarity,
                            'match_snippet': doc_content[:200] + "..." if len(doc_content) > 200 else doc_content
                        }
                        documents.append(doc_result)
            
            logger.info(f"Document search for '{query}' returned {len(documents)} results")
            return documents
            
        except Exception as e:
            logger.error(f"Error in document search: {e}")
            return []
    
    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific document by ID"""
        try:
            if self.documents_collection is None:
                return None
            
            results = self.documents_collection.get(
                ids=[doc_id],
                include=['documents', 'metadatas']
            )
            
            if results['documents'] and results['documents'][0]:
                metadata = results['metadatas'][0]
                content = results['documents'][0]
                
                return {
                    'id': doc_id,
                    'title': metadata.get('title', 'Untitled'),
                    'content': content,
                    'doc_type': metadata.get('doc_type', 'note'),
                    'tags': metadata.get('tags', '').split(',') if metadata.get('tags') else [],
                    'source_url': metadata.get('source_url') or None,
                    'file_path': metadata.get('file_path') or None,
                    'created_at': metadata.get('created_at'),
                    'summary': metadata.get('summary') or None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
            return None
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from vector storage"""
        try:
            if self.documents_collection is None:
                return False
            
            # Get document info first (for file cleanup)
            doc_info = self.get_document_by_id(doc_id)
            
            # Delete from ChromaDB
            self.documents_collection.delete(ids=[doc_id])
            
            # Optionally delete file
            if doc_info and doc_info.get('file_path'):
                try:
                    if os.path.exists(doc_info['file_path']):
                        os.remove(doc_info['file_path'])
                        logger.info(f"Deleted document file: {doc_info['file_path']}")
                except Exception as e:
                    logger.warning(f"Failed to delete document file: {e}")
            
            logger.info(f"Deleted document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    def get_all_documents(self, doc_type: str = None) -> List[Dict[str, Any]]:
        """Get all stored documents, optionally filtered by type"""
        try:
            if self.documents_collection is None:
                return []
            
            search_params = {
                "include": ['documents', 'metadatas']
            }
            
            if doc_type:
                search_params["where"] = {"doc_type": doc_type}
            
            results = self.documents_collection.get(**search_params)
            
            documents = []
            if results['documents']:
                for i, content in enumerate(results['documents']):
                    metadata = results['metadatas'][i]
                    doc_result = {
                        'id': results['ids'][i],
                        'title': metadata.get('title', 'Untitled'),
                        'content': content,
                        'doc_type': metadata.get('doc_type', 'note'),
                        'tags': metadata.get('tags', '').split(',') if metadata.get('tags') else [],
                        'source_url': metadata.get('source_url') or None,
                        'file_path': metadata.get('file_path') or None,
                        'created_at': metadata.get('created_at'),
                        'summary': metadata.get('summary') or None
                    }
                    documents.append(doc_result)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []
    
    # File Watching System
    def _start_file_watcher(self):
        """Start the file watcher thread"""
        try:
            self._watcher_running = True
            self._watcher_thread = threading.Thread(target=self._watch_documents_folder, daemon=True)
            self._watcher_thread.start()
            logger.info("Document file watcher started")
        except Exception as e:
            logger.warning(f"Failed to start file watcher: {e}")
    
    def _stop_file_watcher(self):
        """Stop the file watcher thread"""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1)
    
    def _watch_documents_folder(self):
        """Watch documents folder for file changes"""
        while self._watcher_running:
            try:
                # Check documents folder exists
                if not os.path.exists(self.documents_dir):
                    time.sleep(5)
                    continue
                
                # Scan for markdown files in documents subdirectories
                for root, dirs, files in os.walk(self.documents_dir):
                    for file in files:
                        if file.endswith(('.md', '.txt')):
                            file_path = os.path.join(root, file)
                            try:
                                # Get file modification time
                                mtime = os.path.getmtime(file_path)
                                
                                # Check if file is new or modified
                                if file_path not in self._file_timestamps or self._file_timestamps[file_path] != mtime:
                                    self._file_timestamps[file_path] = mtime
                                    
                                    # Process the file change
                                    self._process_file_change(file_path)
                                    
                            except OSError:
                                # File might have been deleted
                                if file_path in self._file_timestamps:
                                    del self._file_timestamps[file_path]
                                    self._process_file_deletion(file_path)
                
                # Sleep before next check
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
                time.sleep(30)  # Wait longer on error
    
    def _process_file_change(self, file_path: str):
        """Process a changed or new file"""
        try:
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                return
            
            # Parse frontmatter if present
            title = None
            tags = []
            doc_type = "note"
            
            if content.startswith('---'):
                try:
                    # Simple frontmatter parsing
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        content = parts[2].strip()
                        
                        for line in frontmatter.split('\n'):
                            line = line.strip()
                            if line.startswith('title:'):
                                title = line.split(':', 1)[1].strip().strip('"\'')
                            elif line.startswith('tags:'):
                                tags_str = line.split(':', 1)[1].strip()
                                # Parse simple tag list [tag1, tag2] or tag1, tag2
                                tags_str = tags_str.strip('[]')
                                tags = [tag.strip().strip('"\'') for tag in tags_str.split(',') if tag.strip()]
                            elif line.startswith('doc_type:'):
                                doc_type = line.split(':', 1)[1].strip().strip('"\'')
                except:
                    # If frontmatter parsing fails, use whole content
                    pass
            
            # Use filename as title if not found in frontmatter
            if not title:
                title = os.path.splitext(os.path.basename(file_path))[0]
                # Clean up auto-generated filenames
                if title.startswith(('20', '19')) and '_' in title:  # Timestamp-based filename
                    parts = title.split('_', 2)
                    if len(parts) > 2:
                        title = parts[2].replace('_', ' ')
            
            # Generate document ID based on file path
            doc_id = f"file_{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
            
            # Check if document already exists and remove old version
            try:
                if self.documents_collection is not None:
                    existing = self.documents_collection.get(ids=[doc_id])
                    if existing['documents']:
                        self.documents_collection.delete(ids=[doc_id])
            except:
                pass
            
            # Store/update the document
            if self.documents_collection is not None:
                self.documents_collection.add(
                    documents=[content],
                    metadatas=[{
                        'title': title,
                        'doc_type': doc_type,
                        'tags': ','.join(tags),
                        'file_path': file_path,
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat(),
                        'source': 'file_watcher'
                    }],
                    ids=[doc_id]
                )
                logger.info(f"Re-indexed file: {file_path} -> {title}")
            
        except Exception as e:
            logger.error(f"Error processing file change {file_path}: {e}")
    
    def _process_file_deletion(self, file_path: str):
        """Process a deleted file"""
        try:
            # Generate document ID based on file path
            doc_id = f"file_{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
            
            # Remove from ChromaDB
            if self.documents_collection is not None:
                try:
                    self.documents_collection.delete(ids=[doc_id])
                    logger.info(f"Removed deleted file from index: {file_path}")
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error processing file deletion {file_path}: {e}")
    

# Global vector memory manager instance
vector_memory_manager = VectorMemoryManager()