"""
Pydantic models for structured data in MCP tools
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field



class Document(BaseModel):
    """Model for a stored document"""
    id: str = Field(description="Unique document identifier")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content (full text)")
    summary: Optional[str] = Field(default=None, description="Optional document summary")
    tags: List[str] = Field(default_factory=list, description="Document tags for organization")
    doc_type: str = Field(default="note", description="Document type (note, capture, import, pdf)")
    file_path: Optional[str] = Field(default=None, description="Local file path if document is file-based")
    source_url: Optional[str] = Field(default=None, description="Original URL for captured web content")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def to_chromadb_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata format"""
        return {
            'title': self.title,
            'doc_type': self.doc_type,
            'tags': ','.join(self.tags),
            'source_url': self.source_url or '',
            'file_path': self.file_path or '',
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'summary': self.summary or ''
        }
    
    @classmethod
    def from_chromadb(cls, id: str, content: str, metadata: Dict[str, Any]) -> 'Document':
        """Create Document from ChromaDB result"""
        return cls(
            id=id,
            title=metadata.get('title', 'Untitled'),
            content=content,
            summary=metadata.get('summary') or None,
            tags=metadata.get('tags', '').split(',') if metadata.get('tags') else [],
            doc_type=metadata.get('doc_type', 'note'),
            file_path=metadata.get('file_path') or None,
            source_url=metadata.get('source_url') or None,
            created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(metadata.get('updated_at', datetime.now().isoformat())),
            metadata={}
        )


class DocumentSearchResult(BaseModel):
    """Model for document search results"""
    document: Document = Field(description="The matching document")
    relevance_score: float = Field(description="Similarity/relevance score (0.0 to 1.0)")
    match_snippet: Optional[str] = Field(default=None, description="Text snippet showing the match context")