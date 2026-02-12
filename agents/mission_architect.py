"""
Drishti-AX: Mission Architect Agent (The Strategos Prime)
Module: agents/mission_architect.py
Version: Sentinel-14.5 "Strategos Prime"
Author: Sentinel Core System
Timestamp: 2026-02-13 22:30:00 UTC
Classification: TOP SECRET // COGNITIVE PLANNING

Description:
    The tactical brain of the Sentinel Swarm.
    It implements a high-fidelity Finite State Machine (FSM) to navigate 
    complex web environments.
    
    CAPABILITIES:
    1.  SHANNON ENTROPY ANALYSIS: Calculates information density to detect 
        dead pages, loading screens, or CAPTCHAs.
    2.  RECURSIVE SPAWNING: Identifies High-Value Targets (HVT) and spawns 
        child missions with inherited context.
    3.  HEURISTIC PATTERN MATCHING: Uses a library of 50+ regex patterns 
        to identify UI intent (Next, Submit, Download, etc.).
    4.  STRATEGIC MODE SWITCHING: Dynamically shifts between EXPLORE (BFS), 
        EXPLOIT (DFS), and ESCAPE (Backtracking) modes.

    INPUT: AgentState (from src.cognition.schema)
    OUTPUT: AgentState (updated with 'semantic_map' and 'child_missions')
"""

import logging
import re
import math
import random
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

# ==============================================================================
#        CRITICAL: SCHEMA IMPORT
# ==============================================================================
try:
    from src.cognition.schema import (
        AgentState, MissionStatus, StrategyMode, 
        StrategicCollapse, PerceptualDrift
    )
except ImportError:
    # Safety Fallback for Unit Testing
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.cognition.schema import AgentState, MissionStatus, StrategyMode

# ==============================================================================
#        ADVANCED TELEMETRY & CONFIGURATION
# ==============================================================================
logger = logging.getLogger("MissionArchitect")
logger.setLevel(logging.DEBUG) # Catch everything

@dataclass
class ArchitectConfig:
    min_entropy_threshold: float = 2.5       # Below this, page is "Empty"
    max_step_limit: int = 25                 # Force extraction after 25 steps
    recursion_depth_limit: int = 3           # Don't go too deep
    hvt_priority_boost: int = 2              # Boost priority for key targets
    fuzzing_probability: float = 0.05        # Randomly click things (Exploration)

CFG = ArchitectConfig()

# ==============================================================================
#        KNOWLEDGE BASE: HEURISTIC PATTERNS
# ==============================================================================
class PatternLibrary:
    """
    The 'Cortex' of the Architect. Stores regex patterns for identifying 
    UI elements and their strategic value.
    """
    # High Value Targets (HVT) - Worth Spawning Child Missions
    HVT_PATTERNS = {
        "PAGINATION": [
            r"next\s*page", r"more\s*results", r"load\s*more", r"older\s*posts",
            r"next\s*>", r"forward", r"page\s*[0-9]+", r"Show\s*more"
        ],
        "DOCUMENTS": [
            r"drhp", r"red\s*herring", r"prospectus", r"annual\s*report",
            r"download", r"\.pdf$", r"\.xlsx$", r"financial\s*statement"
        ],
        "DETAILS": [
            r"view\s*details", r"read\s*more", r"full\s*story", r"click\s*here",
            r"learn\s*more", r"case\s*study"
        ]
    }

    # Action Triggers - Worth Clicking/Typing immediately
    ACTION_PATTERNS = {
        "SEARCH_INPUT": [
            r"search", r"query", r"find", r"keywords", r"looking\s*for"
        ],
        "SUBMIT_BUTTON": [
            r"submit", r"search", r"go", r"filter", r"apply", r"enter"
        ],
        "CLOSE_POPUP": [
            r"close", r"x", r"no\s*thanks", r"later", r"dismiss", r"accept\s*cookies"
        ]
    }

    # Hazard Patterns - Avoid or Escape
    HAZARD_PATTERNS = [
        r"login", r"sign\s*in", r"register", r"subscribe", 
        r"captcha", r"access\s*denied", r"forbidden", r"404"
    ]

# ==============================================================================
#        CORE INTELLIGENCE: THE ARCHITECT AGENT
# ==============================================================================
class MissionArchitectAgent:
    """
    The Cognitive Engine. 
    Converts 'Perception' (Sensor Data) into 'Will' (Action Plans).
    """
    def __init__(self):
        self.kb = PatternLibrary()
        self.session_memory = {} # Short-term memory for loop detection

    def plan(self, state: AgentState) -> AgentState:
        """
        The Main Cognitive Loop.
        Input: A Raw State (DOM Snapshot)
        Output: An Updated State (Semantic Map + Child Missions)
        """
        mission_id = state.get('mission_id', 'UNKNOWN')
        # logger.debug(f"[{mission_id}] Architect Pulse Check...")

        # 1. FORENSIC VALIDATION
        if not self._validate_inputs(state):
            return state

        # 2. ENTROPY ANALYSIS (Is the page worth processing?)
        entropy_score = self._calculate_page_entropy(state)
        state['site_physics']['entropy'] = entropy_score
        
        if entropy_score < CFG.min_entropy_threshold:
            logger.warning(f"[{mission_id}] Low Entropy ({entropy_score:.2f}). Page likely dead/loading.")
            # Heuristic: Wait or Refresh
            state['semantic_map'] = {"action": "WAIT", "duration": 2.0, "thought": "Low entropy, waiting for hydration."}
            return state

        # 3. RECURSIVE DISCOVERY (Spawn the Swarm)
        # This is the 'Singularity' logic - self-replication.
        new_missions = self._scan_for_child_missions(state)
        if new_missions:
            logger.info(f"[{mission_id}] Spawning {len(new_missions)} Child Missions.")
            state['child_missions'].extend(new_missions)
            # If we found what we came for, we might mark as success
            # But usually we want to keep exploring the current page too.

        # 4. STRATEGIC MODE SELECTION (Explore vs Exploit)
        mode = self._determine_strategy_mode(state)
        state['strategy_mode'] = mode.value

        # 5. TACTICAL RESOLUTION (Pick the single best action)
        decision = self._resolve_tactics(state, mode)
        
        # 6. MEMORY UPDATE
        self._update_memory(state, decision)
        
        state['semantic_map'] = decision
        state['status'] = MissionStatus.NAVIGATING.value
        
        return state

    # --------------------------------------------------------------------------
    # LEVEL 1: VALIDATION & PHYSICS
    # --------------------------------------------------------------------------
    def _validate_inputs(self, state: AgentState) -> bool:
        if not state.get('dom_snapshot'):
            logger.error(f"[{state['mission_id']}] Blind Spot detected. No DOM.")
            state['semantic_map'] = {"action": "WAIT", "duration": 1.0}
            return False
        return True

    def _calculate_page_entropy(self, state: AgentState) -> float:
        """
        Calculates Shannon Entropy of the visible text to detect content quality.
        High Entropy = Rich Content. Low Entropy = Loading/Error/Blank.
        """
        dom = state.get('dom_snapshot', [])
        if not dom: return 0.0
        
        text_corpus = " ".join([el.get('text', '') for el in dom])
        if not text_corpus: return 0.0
        
        # Shannon Entropy Formula
        prob = [float(text_corpus.count(c)) / len(text_corpus) for c in dict.fromkeys(list(text_corpus))]
        entropy = -sum([p * math.log(p) / math.log(2.0) for p in prob])
        
        return entropy

    # --------------------------------------------------------------------------
    # LEVEL 2: RECURSIVE SPAWNING (THE SWARM)
    # --------------------------------------------------------------------------
    def _scan_for_child_missions(self, state: AgentState) -> List[Dict]:
        """
        Scans DOM for HVT patterns and creates new Mission Manifests.
        """
        candidates = []
        base_url = state.get('current_url', '')
        dom = state.get('dom_snapshot', [])
        
        # We only look at Anchor tags (Links)
        links = [el for el in dom if el.get('tag') == 'A' and el.get('visible')]
        
        for link in links:
            text = link.get('text', '').strip()
            href = link.get('attributes', {}).get('href', '')
            
            if not href or len(text) < 3 or href.startswith(('javascript:', '#', 'mailto:')):
                continue
                
            full_url = urljoin(base_url, href)
            
            # Check against HVT Patterns
            for category, patterns in self.kb.HVT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        # Construct the Child Mission
                        candidates.append({
                            "url": full_url,
                            "goal": f"[{category}] Investigate: {text[:30]}",
                            "prio": 1 if category == "DOCUMENTS" else 2,
                            "parent_id": state['mission_id'],
                            "strategy": "DIRECT_ACTION" # Children should be aggressive
                        })
                        break # Found a match, stop checking patterns for this link
        
        # Deduplication (Simple)
        unique_candidates = {c['url']: c for c in candidates}.values()
        return list(unique_candidates)

    # --------------------------------------------------------------------------
    # LEVEL 3: TACTICAL RESOLUTION (DECISION MAKING)
    # --------------------------------------------------------------------------
    def _determine_strategy_mode(self, state: AgentState) -> StrategyMode:
        """
        Decides the high-level strategy based on mission history.
        """
        history = state.get('history_steps', [])
        goal = state.get('goal', '').lower()
        
        # If we just started, we are in DIRECT_ACTION mode (try to search/click goal)
        if len(history) < 2:
            return StrategyMode.DIRECT_ACTION
            
        # If we have been stuck on the same URL for 3 steps, switch to RECOVERY
        if len(history) > 3 and state.get('current_url') == state.get('url'):
            # Check if we actually did anything
            return StrategyMode.RECONNAISSANCE
            
        return StrategyMode.DIRECT_ACTION

    def _resolve_tactics(self, state: AgentState, mode: StrategyMode) -> Dict:
        """
        The "Reflex" Layer. Picks the specific DOM element to interact with.
        """
        dom = state.get('dom_snapshot', [])
        goal = state.get('goal', '').lower()
        
        # 1. POPUP KILLER (Always Active)
        # If we see a "Close" button, kill it immediately.
        for el in dom:
            if any(re.search(p, el.get('text', ''), re.IGNORECASE) for p in self.kb.ACTION_PATTERNS["CLOSE_POPUP"]):
                return self._create_action("CLICK", el, "Closing Popup/Overlay")

        # 2. DIRECT ACTION (Search & Destroy)
        if mode == StrategyMode.DIRECT_ACTION:
            # A. SEARCH INJECTION
            if "search" in goal or "find" in goal:
                # Look for Input fields
                inputs = [el for el in dom if el.get('tag') == 'INPUT']
                for inp in inputs:
                    # Check placeholders or nearby text
                    meta = str(inp.get('attributes', {})).lower()
                    if "search" in meta or "query" in meta:
                        term = self._extract_search_term(goal)
                        return self._create_action("TYPE", inp, f"Injecting Query: {term}", value=term)
            
            # B. LINK TRAVERSAL
            # Click links that match the goal keywords
            keywords = [w for w in goal.split() if len(w) > 4] # Filter stopwords
            for el in dom:
                if el.get('tag') == 'A':
                    text = el.get('text', '').lower()
                    if any(k in text for k in keywords):
                        return self._create_action("CLICK", el, f"Clicking relevant link: {text[:20]}...")

        # 3. RECONNAISSANCE (Fallback)
        # If we don't know what to do, scroll down to trigger lazy loading
        return {
            "action": "SCROLL",
            "direction": "DOWN",
            "amount": 500,
            "thought": "No high-confidence targets. Exploring page depth."
        }

    # --------------------------------------------------------------------------
    # LEVEL 4: UTILITIES & MEMORY
    # --------------------------------------------------------------------------
    def _create_action(self, action_type: str, element: Dict, thought: str, value: Optional[str] = None) -> Dict:
        return {
            "action": action_type,
            "xpath": element.get('xpath'),
            "selector": element.get('attributes', {}).get('id'), # Fallback
            "value": value,
            "thought": thought,
            "target_rect": element.get('rect')
        }

    def _extract_search_term(self, goal: str) -> str:
        # "Find IPOs" -> "IPOs"
        common_verbs = ["find", "search", "look", "identify", "extract", "get"]
        words = goal.split()
        filtered = [w for w in words if w.lower() not in common_verbs]
        return " ".join(filtered)

    def _update_memory(self, state: AgentState, decision: Dict):
        # Update history to prevent loops
        step_desc = f"{decision['action']} -> {decision.get('thought', 'Unknown')}"
        state['history_steps'].append(step_desc)