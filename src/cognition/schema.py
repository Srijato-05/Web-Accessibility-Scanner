"""
Drishti-AX: Shared Intelligence Schema
Module: src.cognition.schema
Version: Sentinel-14.4 "Foundation"
Author: Sentinel Core System
Timestamp: 2026-02-13 21:00:00 UTC
Classification: TOP SECRET // AUTONOMOUS LOGIC

Description:
    The universal data contract for the Sentinel swarm.
    This file defines the 'Mental Model' shared by the Architect, Sensor, 
    Navigator, and Orchestrator.
"""

from typing import TypedDict, List, Dict, Optional, Any, Union
from enum import Enum
from datetime import datetime

# ==============================================================================
#        SYSTEM ENUMERATIONS (THE STATE MACHINE)
# ==============================================================================

class MissionStatus(Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ZOMBIE = "ZOMBIE"

class StrategyMode(Enum):
    DIRECT_ACTION = "DIRECT_ACTION"     # Fast, heuristic-based
    RECONNAISSANCE = "RECONNAISSANCE"   # Exploration, menu-clicking
    ATTRITION = "ATTRITION"             # Systematic element testing
    RECOVERY = "RECOVERY"               # Back/Refresh logic

# ==============================================================================
#        CORE SCHEMA DEFINITION
# ==============================================================================

class AgentState(TypedDict, total=False):
    """
    The Shared Memory structure of a single Autonomous Mission.
    Performance Optimized for high-frequency updates.
    """
    # 1. Identification & Hierarchy
    mission_id: str
    parent_mission_id: Optional[str]    # Recursive tasking link
    prime_directive: str                # The high-level user goal
    goal: str                           # The specific task-level goal
    
    # 2. Navigation State
    url: str                            # Entry Point
    current_url: str                    # Actual Browser Location
    status: Union[str, MissionStatus]   # Current Lifecycle Phase
    
    # 3. Perception (Sensor Data)
    dom_snapshot: List[Dict[str, Any]]  # Filtered interactive elements
    perception_meta: Dict[str, Any]     # Scan time, complexity scores, etc.
    site_physics: Dict[str, Any]        # Latency modifiers, framework tags
    
    # 4. Cognition (Architect Data)
    semantic_map: Dict[str, Any]        # The current 'Decision' object
    strategy_mode: Union[str, StrategyMode]
    history_steps: List[str]            # Audit trail of actions taken
    child_missions: List[Dict[str, Any]] # Missions to spawn after completion
    
    # 5. Resilience & Forensics
    error_log: List[str]                # Detailed failure messages
    hard_blacklist: Dict[str, List[str]] # {"xpaths": [], "ids": []}
    input_data: Optional[str]           # Persistent typing payloads
    
    # 6. Temporal Data
    start_time: float
    last_update: float
    step_count: int
    max_steps: int

# ==============================================================================
#        NEURAL ERROR HANDLING (SPECIFIC SIGNALS)
# ==============================================================================

class SentinelSwarmError(Exception):
    """Base class for all Swarm-related exceptions."""
    def __init__(self, message: str, state: Optional[AgentState] = None):
        self.state = state
        super().__init__(message)

class StrategicCollapse(SentinelSwarmError):
    """Raised when the Architect cannot find a viable path to victory."""
    pass

class PerceptualDrift(SentinelSwarmError):
    """Raised when the Sensor detects the page has changed in an unhandled way."""
    pass

class KineticInterference(SentinelSwarmError):
    """Raised when the Navigator is physically blocked from interacting (e.g., popups)."""
    pass

class OvermindPenalty(SentinelSwarmError):
    """Raised when the Global Overmind forces a mission to halt."""
    pass

# ==============================================================================
#        UTILITIES (DYNAMIC VALIDATION)
# ==============================================================================

def initialize_empty_state(mission_id: str, url: str, goal: str) -> AgentState:
    """
    Factory function to create a clean, compliant state object.
    """
    import time
    return {
        "mission_id": mission_id,
        "url": url,
        "current_url": url,
        "goal": goal,
        "status": MissionStatus.STARTED.value,
        "history_steps": [],
        "error_log": [],
        "dom_snapshot": [],
        "semantic_map": {},
        "hard_blacklist": {"xpaths": [], "ids": []},
        "child_missions": [],
        "site_physics": {"latency": 1.0},
        "start_time": time.time(),
        "step_count": 0,
        "max_steps": 25
    }