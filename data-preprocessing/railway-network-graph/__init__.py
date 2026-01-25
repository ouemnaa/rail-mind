"""
Rail Network Graph Module
=========================
Graph-based network representation for Italian railways.
Supports: Conflict Detection, Resolution Generation, What-If Simulation.

Author: AI Rail Network Brain Team
Date: January 2026
"""

from .graph_builder import RailNetworkGraph
from .config import GRAPH_CONFIG

__all__ = ['RailNetworkGraph', 'GRAPH_CONFIG']
