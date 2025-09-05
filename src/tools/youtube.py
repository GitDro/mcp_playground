"""
YouTube video analysis and transcript handling tools

Supports large context windows (24K+ tokens) for comprehensive video analysis.
"""

import os
import random
import requests
from typing import Optional
from datetime import datetime

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from src.core.unified_cache import get_cached_data, save_cached_data
from src.core.utils import extract_video_id, filter_sponsor_content
from src.core.mcp_output import create_text_result
import logging

logger = logging.getLogger(__name__)


def get_webshare_proxy():
    """Get a random WebShare proxy from environment variables"""
    proxy_list = os.getenv('WEBSHARE_PROXIES', '').split(',')
    if not proxy_list or proxy_list == ['']:
        return None
    
    try:
        proxy = random.choice(proxy_list).strip()
        if not proxy:
            return None
            
        ip, port, username, password = proxy.split(':')
        return {
            'http': f'http://{username}:{password}@{ip}:{port}',
            'https': f'http://{username}:{password}@{ip}:{port}'
        }
    except Exception as e:
        logger.warning(f"Error parsing WebShare proxy: {e}")
        return None


def create_proxy_session():
    """Create a requests session with proxy and browser headers"""
    session = requests.Session()
    
    # Try to get WebShare proxy
    proxy = get_webshare_proxy()
    if proxy:
        session.proxies.update(proxy)
        logger.info("Using WebShare proxy for YouTube requests")
    
    # Add realistic browser headers to avoid bot detection
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    return session


def register_youtube_tools(mcp: FastMCP):
    """Register YouTube-related tools with the MCP server"""
    
    @mcp.tool(description="Get YouTube video transcript and analyze content with optional specific questions")
    def analyze_youtube_url(url: str, question: str = "") -> ToolResult:
        """Analyze YouTube video content from YouTube URLs. Provide just a YouTube URL for a comprehensive summary, or include a specific question to get targeted answers about the video content. Handles videos up to 2-3 hours with adaptive context management.
        
        Args:
            url: YouTube video URL (e.g., "https://youtube.com/watch?v=...")
            question: Optional specific question about the video content (e.g., "What are the key points about AI?")
        """
        try:
            # Validate URL first
            if not url or not isinstance(url, str):
                return create_text_result("Error: Please provide a valid YouTube URL.")
            
            # Basic YouTube URL validation
            url = url.strip()
            if not any(domain in url for domain in ['youtube.com', 'youtu.be', 'm.youtube.com']):
                return create_text_result("Error: Please provide a valid YouTube URL (youtube.com or youtu.be).")
            
            # Get the transcript
            transcript_result = _get_youtube_transcript(url)
            
            # Check for error conditions
            if any(transcript_result.startswith(prefix) for prefix in ["Error", "Invalid", "No transcript"]):
                return create_text_result(transcript_result)
            
            # Extract title and transcript text  
            lines = transcript_result.split('\n', 2)
            title = lines[0].replace('**', '') if lines else "YouTube Video"
            transcript_text = lines[2] if len(lines) > 2 else transcript_result
            
            # Filter out sponsor/ad content
            transcript_text = filter_sponsor_content(transcript_text)
            
            # Calculate basic stats
            word_count = len(transcript_text.split())
            duration_estimate = f"~{word_count // 150} minutes" if word_count > 150 else "< 1 minute"
            
            # Process content with adaptive truncation
            content, note = _process_transcript_content(transcript_text)
            
            # Determine analysis mode and format output
            if question.strip():
                # Targeted question mode
                return create_text_result(_format_question_response(title, duration_estimate, word_count, content, note, question))
            else:
                # Summary mode
                return create_text_result(_format_summary_response(title, duration_estimate, word_count, content, note))
                
        except Exception as e:
            return create_text_result(f"Error analyzing YouTube video: {str(e)}. Please check that the URL is valid and the video has available transcripts.")


def _get_youtube_transcript(url: str) -> str:
    """Internal function to extract transcript from YouTube video with caching"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Extract video ID
        video_id = extract_video_id(url)
        if not video_id:
            return f"Invalid YouTube URL. Please provide a valid YouTube video URL."
        
        # Check cache first
        cache_key = f"youtube_transcript_{video_id}"
        cached_data = get_cached_data(cache_key, "youtube_transcript")
        if cached_data:
            return f"**{cached_data.get('title', 'YouTube Video')}**\n\n{cached_data['transcript']}"
        
        # Configure session for proxy if needed, otherwise use default
        session = create_proxy_session()
        use_proxy_session = bool(session.proxies)  # Only use custom session if proxies are configured
        
        # Get transcript from YouTube with multiple retry strategies
        transcript_text = None
        error_messages = []
        
        # Get transcript using correct 2025 API (instance methods)
        import time
        
        # Add delay to avoid rate limiting
        time.sleep(1.0)
        
        # Strategy 1: Direct fetch (with or without proxy session)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            if use_proxy_session:
                api = YouTubeTranscriptApi(http_client=session)
            else:
                api = YouTubeTranscriptApi()  # Use default session
            
            transcript = api.fetch(video_id, languages=['en'])
            transcript_text = ' '.join([entry.text for entry in transcript])
        except Exception as e:
            error_messages.append(f"Direct English fetch failed: {str(e)}")
            
            # Strategy 2: List available transcripts and select best one
            try:
                if use_proxy_session:
                    api = YouTubeTranscriptApi(http_client=session)
                else:
                    api = YouTubeTranscriptApi()  # Use default session
                    
                transcript_list = api.list(video_id)
                
                # Try to find English manual transcript first
                try:
                    transcript = transcript_list.find_manually_created_transcript(['en'])
                    transcript_data = transcript.fetch()
                    transcript_text = ' '.join([entry.text for entry in transcript_data])
                except:
                    # Try English auto-generated
                    try:
                        transcript = transcript_list.find_generated_transcript(['en'])
                        transcript_data = transcript.fetch()
                        transcript_text = ' '.join([entry.text for entry in transcript_data])
                    except:
                        # Try any available transcript
                        try:
                            available_transcripts = list(transcript_list)
                            if available_transcripts:
                                first_transcript = available_transcripts[0]
                                transcript_data = first_transcript.fetch()
                                transcript_text = ' '.join([entry.text for entry in transcript_data])
                        except Exception as e3:
                            error_messages.append(f"Any transcript fetch failed: {str(e3)}")
            except Exception as e2:
                error_messages.append(f"List transcripts failed: {str(e2)}")
        
        if not transcript_text:
            return f"Error accessing video transcripts: \n{'. '.join(error_messages)}. The video may be private, age-restricted, or have no captions available."
        
        # Try to get video title (basic approach)
        title = f"YouTube Video ({video_id})"
        
        # Cache the transcript
        cache_data = {
            'video_id': video_id,
            'url': url,
            'title': title,
            'transcript': transcript_text,
            'language': 'en'
        }
        save_cached_data(cache_key, cache_data, "youtube_transcript", {'video_id': video_id})
        
        return f"**{title}**\n\n{transcript_text}"
        
    except Exception as e:
        return f"Error processing YouTube URL: {str(e)}. Please verify the URL is correct and accessible."


def _process_transcript_content(transcript_text: str) -> tuple[str, str]:
    """Process transcript with adaptive truncation strategy"""
    import os
    
    # Default to 24K tokens ≈ 96K characters (configurable via env var)
    max_tokens = int(os.getenv('YOUTUBE_MAX_TOKENS', '24000'))
    max_content_length = max_tokens * 4  # Rough estimate: 1 token ≈ 4 characters
    
    if len(transcript_text) <= max_content_length:
        return transcript_text, ""
    
    # Adaptive truncation strategy based on how much content exceeds limit
    original_length = len(transcript_text)
    overflow_ratio = original_length / max_content_length
    
    # Determine truncation percentages based on how much we're over limit
    if overflow_ratio <= 1.5:  # Moderately long (up to 1.5x limit)
        beginning_pct, end_pct = 0.50, 0.30  # 80% of limit
    elif overflow_ratio <= 3.0:  # Very long (up to 3x limit) 
        beginning_pct, end_pct = 0.35, 0.25  # 60% of limit
    elif overflow_ratio <= 5.0:  # Extremely long (up to 5x limit)
        beginning_pct, end_pct = 0.25, 0.20  # 45% of limit
    else:  # Massive videos (5x+ limit)
        beginning_pct, end_pct = 0.20, 0.15  # 35% of limit
    
    # Calculate actual character limits
    beginning_chars = int(max_content_length * beginning_pct)
    end_chars = int(max_content_length * end_pct)
    
    # Get beginning and end portions
    beginning = transcript_text[:beginning_chars]
    end_text = transcript_text[-end_chars:] if end_chars < len(transcript_text) else transcript_text
    
    # Ensure no overlap (shouldn't happen with these ratios, but safety check)
    if beginning_chars + end_chars >= original_length:
        content = beginning
        note = f"\n\n*Note: Video is {overflow_ratio:.1f}x the {max_tokens:,} token limit. Showing first {beginning_chars:,} characters only.*"
    else:
        content = f"{beginning}\n\n--- [MIDDLE SECTION OMITTED - VIDEO {overflow_ratio:.1f}X CONTEXT LIMIT] ---\n\n{end_text}"
        omitted_chars = original_length - beginning_chars - end_chars
        omitted_pct = (omitted_chars / original_length) * 100
        note = f"\n\n*Note: Video is {overflow_ratio:.1f}x the {max_tokens:,} token limit. Showing beginning ({beginning_pct*100:.0f}%) and ending ({end_pct*100:.0f}%). Omitted {omitted_pct:.0f}% of content ({omitted_chars:,} chars).*"
    
    return content, note


def _format_summary_response(title: str, duration_estimate: str, word_count: int, content: str, note: str) -> str:
    """Format response for general video summary"""
    return f"""## 📺 Video Analysis Request

**{title}** ({duration_estimate}, {word_count:,} words)

I'll analyze this video content and provide a focused summary covering the main points, key insights, and conclusions.

---

<details>
<summary>📄 Video Transcript (Click to expand)</summary>

{content}{note}

</details>

---

**Analysis Instructions:** Provide a concise summary focusing on the main content, key points, and conclusions. Ignore any sponsor mentions, advertisements, or channel promotion content."""


def _format_question_response(title: str, duration_estimate: str, word_count: int, content: str, note: str, question: str) -> str:
    """Format response for specific question about video"""
    return f"""## 📺 Video Q&A Request

**{title}** ({duration_estimate}, {word_count:,} words)

**Your Question:** "{question}"

I'll analyze the video content to answer your specific question.

---

<details>
<summary>📄 Video Transcript (Click to expand)</summary>

{content}{note}

</details>

---

**Analysis Instructions:** Focus on answering "{question}" based on the main video content. Ignore any sponsor mentions, advertisements, or channel promotion content."""