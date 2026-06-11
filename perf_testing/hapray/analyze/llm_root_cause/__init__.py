"""
LLM-powered root cause analysis for HapRay performance reports.

Provides automated root cause analysis for performance issues (empty frames,
CPU hotspots, frame load, threads, IPC, SO load, memory, component reuse,
etc.) by combining deterministic multi-signal evidence extraction with LLM
reasoning.
"""

from .runner import apply_agent_result_to_report, run_comprehensive_analysis, run_empty_frame_analysis

__all__ = ['apply_agent_result_to_report', 'run_comprehensive_analysis', 'run_empty_frame_analysis']
