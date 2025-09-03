"""
YouTube video analysis and transcript handling tools

Supports large context windows (24K+ tokens) for comprehensive video analysis.
"""

from typing import Optional
from datetime import datetime

from fastmcp import FastMCP
from ..core.unified_cache import get_cached_data, save_cached_data
from ..core.utils import extract_video_id, filter_sponsor_content


def register_youtube_tools(mcp: FastMCP):
    """Register YouTube-related tools with the MCP server"""
    
    @mcp.tool(description="Analyze YouTube video content from YouTube URLs")
    def analyze_youtube_url(url: str, question: str = "") -> str:
        """Analyze YouTube video content from YouTube URLs. Provide just a YouTube URL for a comprehensive summary, or include a specific question to get targeted answers about the video content. Handles videos up to 2-3 hours with adaptive context management.
        
        Args:
            url: YouTube video URL (e.g., "https://youtube.com/watch?v=...")
            question: Optional specific question about the video content (e.g., "What are the key points about AI?")
        """
        try:
            # Get the transcript
            transcript_result = _get_youtube_transcript(url)
            
            if transcript_result.startswith("Error") or transcript_result.startswith("Invalid") or transcript_result.startswith("No transcript"):
                return transcript_result
            
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
                return _format_question_response(title, duration_estimate, word_count, content, note, question)
            else:
                # Summary mode
                return _format_summary_response(title, duration_estimate, word_count, content, note)
                
        except Exception as e:
            return f"Error analyzing video: {str(e)}"


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
        
        # Get transcript from YouTube
        try:
            # First try to get the default transcript using newer API
            api = YouTubeTranscriptApi()
            transcript_list = api.fetch(video_id)
            transcript_text = ' '.join([entry.text for entry in transcript_list])
        except Exception as e:
            # Try to get any available transcript (auto-generated, different languages, etc.)
            try:
                api = YouTubeTranscriptApi()
                transcript_list_obj = api.list(video_id)
                
                # First try to find English transcript (manual or auto-generated)
                try:
                    transcript = transcript_list_obj.find_transcript(['en', 'en-US', 'en-GB'])
                    transcript_data = transcript.fetch()
                    transcript_text = ' '.join([entry.text for entry in transcript_data])
                except:
                    # If no English, try any available transcript
                    available_transcripts = list(transcript_list_obj)
                    if available_transcripts:
                        transcript_data = available_transcripts[0].fetch()
                        transcript_text = ' '.join([entry.text for entry in transcript_data])
                    else:
                        return f"No transcript available for this video. The video may not have captions or subtitles."
            except Exception as e2:
                return f"No transcript available for this video. The video may not have captions or subtitles."
        
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
        return f"Error extracting transcript: {str(e)}"


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