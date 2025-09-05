"""
MCP content block utilities for proper client rendering

This module provides utilities to generate proper MCP content blocks that render
correctly in different clients (IDEs, Streamlit, etc.) by following the MCP specification.

Key principles:
- Use TextContent for human-readable markdown
- Use ImageContent for charts (enables direct display in IDEs)
- Avoid redundant structured_content to save tokens
- Only use structured_content when it provides unique machine-readable value
"""

from typing import List, Dict, Any, Optional, Union
import base64
import io
from mcp.types import TextContent, ImageContent, ContentBlock, Annotations
from fastmcp.tools.tool import ToolResult

def create_text_content(
    text: str,
    mime_type: str = "text/markdown",
    audience: Optional[List[str]] = None,
    priority: Optional[float] = None
) -> TextContent:
    """
    Create a TextContent block with proper annotations.
    
    Args:
        text: The text content
        mime_type: MIME type (default: text/markdown)
        audience: Target audience ["user", "assistant"] or None for both
        priority: Priority from 0.0 to 1.0 (1.0 = highest priority)
    """
    annotations = None
    if audience is not None or priority is not None:
        annotations = Annotations(
            audience=audience,
            priority=priority
        )
    
    return TextContent(
        type="text",
        text=text,
        annotations=annotations,
        mimeType=mime_type
    )

def create_image_content(
    image_data: Union[str, bytes],
    mime_type: str = "image/png",
    audience: Optional[List[str]] = None,
    priority: Optional[float] = None
) -> ImageContent:
    """
    Create an ImageContent block from base64 string or raw bytes.
    
    Args:
        image_data: Base64 string (with or without data: prefix) or raw bytes
        mime_type: MIME type (default: image/png)  
        audience: Target audience ["user", "assistant"] or None for both
        priority: Priority from 0.0 to 1.0
    """
    annotations = None
    if audience is not None or priority is not None:
        annotations = Annotations(
            audience=audience,
            priority=priority
        )
    
    # Handle different input formats
    if isinstance(image_data, bytes):
        # Convert bytes to base64
        data = base64.b64encode(image_data).decode('utf-8')
    elif isinstance(image_data, str):
        # Remove data URI prefix if present
        if image_data.startswith('data:'):
            data = image_data.split(',', 1)[1]
        else:
            data = image_data
    else:
        raise ValueError(f"Unsupported image_data type: {type(image_data)}")
    
    return ImageContent(
        type="image",
        data=data,
        mimeType=mime_type,
        annotations=annotations
    )

def create_summary_and_chart_result(
    summary_text: str,
    chart_base64: Optional[str] = None,
    chart_title: str = "Chart"
) -> ToolResult:
    """
    Create a ToolResult with proper content blocks for summary + chart pattern.
    
    This pattern provides:
    - Short summary marked for user display (high priority)
    - Chart as separate ImageContent block (if provided)
    - No redundant structured data (avoids token waste)
    
    Args:
        summary_text: Markdown-formatted summary for user display
        chart_base64: Base64 chart data (with or without data: prefix)
        chart_title: Title for the chart (used in alt text)
    """
    content_blocks: List[ContentBlock] = []
    
    # User-facing summary with high priority
    content_blocks.append(
        create_text_content(
            text=summary_text,
            mime_type="text/markdown", 
            audience=None,  # Both user and assistant can see
            priority=1.0
        )
    )
    
    # Chart as separate image block (if provided)
    if chart_base64:
        content_blocks.append(
            create_image_content(
                image_data=chart_base64,
                mime_type="image/png",
                audience=["user"],  # Charts only for user display
                priority=0.8
            )
        )
    
    return ToolResult(
        content=content_blocks
    )

def create_table_result(
    title: str,
    table_markdown: str
) -> ToolResult:
    """
    Create a ToolResult for table data with proper content blocks.
    
    Args:
        title: Title/summary for the table
        table_markdown: Markdown-formatted table
    """
    # Combine title and table
    full_text = f"## {title}\n\n{table_markdown}"
    
    content_blocks = [
        create_text_content(
            text=full_text,
            mime_type="text/markdown",
            audience=None,  # Both user and assistant can see
            priority=1.0
        )
    ]
    
    return ToolResult(
        content=content_blocks
    )

def create_text_result(text: str) -> ToolResult:
    """
    Create a simple ToolResult with just markdown text content.
    
    Use this for simple tools that only return text without charts.
    
    Args:
        text: Markdown-formatted text
    """
    return ToolResult(
        content=[
            create_text_content(
                text=text,
                mime_type="text/markdown",
                audience=None,  # Both user and assistant can see
                priority=1.0
            )
        ]
    )

def extract_chart_from_matplotlib() -> Optional[str]:
    """
    Extract base64 PNG data from current matplotlib figure.
    
    Returns:
        Base64 string without data URI prefix, or None if error
    """
    try:
        import matplotlib.pyplot as plt
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        buffer.seek(0)
        
        plot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        buffer.close()
        
        return plot_data
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error extracting matplotlib chart: {e}")
        return None

# Backward compatibility helpers
def convert_markdown_with_base64_to_content_blocks(
    markdown_text: str
) -> ToolResult:
    """
    Convert existing markdown with embedded base64 images to proper content blocks.
    
    This helper can be used to gradually migrate existing tools.
    
    Args:
        markdown_text: Markdown text that may contain ![](data:image/png;base64,...)
    """
    import re
    
    # Extract base64 images from markdown
    img_pattern = r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)'
    images = re.findall(img_pattern, markdown_text)
    
    # Remove images from markdown text
    text_only = re.sub(img_pattern, lambda m: f"*[Chart: {m.group(1) or 'Visualization'}]*", markdown_text)
    
    content_blocks: List[ContentBlock] = []
    
    # Add text content
    content_blocks.append(
        create_text_content(
            text=text_only.strip(),
            mime_type="text/markdown",
            audience=None,  # Both user and assistant can see
            priority=1.0
        )
    )
    
    # Add images as separate blocks
    for alt_text, img_format, base64_data in images:
        content_blocks.append(
            create_image_content(
                image_data=base64_data,
                mime_type=f"image/{img_format}",
                audience=["user"],  # Charts only for user display
                priority=0.8
            )
        )
    
    return ToolResult(
        content=content_blocks
    )