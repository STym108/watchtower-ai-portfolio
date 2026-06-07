"""
WatchTower.ai Unified ML Engine Package
=======================================
Exposes the primary OfflineVideoPipeline interface to other components (like FastAPI backend).
"""

from .pipelineY import OfflineVideoPipeline

__all__ = ["OfflineVideoPipeline"]
