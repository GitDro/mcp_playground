"""
Pydantic models for structured data in MCP tools
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SectionAnalysis(BaseModel):
    """Analysis of a single paper section"""
    bullet_points: List[str] = Field(
        description="2-3 concise bullet points with key insights",
        min_length=1,
        max_length=3
    )


class PaperAnalysis(BaseModel):
    """Complete structured analysis of a research paper"""
    introduction: Optional[SectionAnalysis] = Field(
        default=None,
        description="Main problem, key contribution, and novelty"
    )
    methods: Optional[SectionAnalysis] = Field(
        default=None,
        description="Novel techniques, innovations, and unique aspects"
    )
    results: Optional[SectionAnalysis] = Field(
        default=None,
        description="Performance improvements, comparisons, and metrics"
    )
    discussion: Optional[SectionAnalysis] = Field(
        default=None,
        description="Conclusions, limitations, and future work"
    )