"""
LLM-powered root cause analysis for HapRay performance reports.

Provides automated root cause analysis for empty frame (空刷) issues
by combining deterministic evidence extraction with LLM reasoning.
"""

from .runner import apply_agent_result_to_report, run_empty_frame_analysis

__all__ = ['apply_agent_result_to_report', 'run_empty_frame_analysis']
