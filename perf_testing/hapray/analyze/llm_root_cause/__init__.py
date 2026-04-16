"""
LLM-powered root cause analysis for HapRay performance reports.

Provides automated root cause analysis for empty frame (空刷) issues
by combining deterministic evidence extraction with LLM reasoning.
"""

from .runner import run_empty_frame_analysis

__all__ = ["run_empty_frame_analysis"]
