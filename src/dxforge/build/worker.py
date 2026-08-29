"""Inline build runner; queue-based execution plugs in here without touching the pipeline."""

from dxforge.build.pipeline import run_build

__all__ = ["run_build"]
