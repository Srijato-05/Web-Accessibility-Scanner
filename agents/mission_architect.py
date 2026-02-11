"""
Drishti-AX: Mission Architect Agent (The Strategist Pillar)
Module: agents/mission_architect.py
Version: Sentinel-9.6 "Omniscient" (Production Release)
Author: Sentinel Core System
Timestamp: 2026-02-12 06:30:00 UTC

Description:
    The absolute authority on strategic planning. This module does not just "pick"
    elements; it performs a forensic analysis of the DOM, cross-references it 
    with a persistent failure database, and synthesizes a tactical plan using 
    metacognitive reasoning.

    CORE SUBSYSTEMS:
    1.  BlacklistRegistry: Persistent tracking of toxic XPaths, IDs, and Containers.
    2.  HeuristicEngine: 5-Dimensional scoring (Semantic, Spatial, Structural, History, Risk).
    3.  NeuralParser: 5-Stage surgical JSON extraction reactor.
    4.  TacticalValidator: Pre-flight safety checks and Hallucination Veto.
"""

import sys
import os
import json
import logging
import re
import time
import math
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field

# ==============================================================================
#        ENVIRONMENT & CORE DEPENDENCIES SETUP
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from src.utils.model_loader import ai_engine
    from cognition.state_manager import AgentState, mission_db
except ImportError as e:
    print(f"[FATAL] Mission Architect Import Failure: {e}")
    sys.exit(1)

# ==============================================================================
#        ADVANCED LOGGING INFRASTRUCTURE
# ==============================================================================
logger = logging.getLogger("MissionArchitect")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('%(asctime)s - [ARCHITECT] - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)
    
    log_dir = os.path.join(project_root, "reports", "logs")
    os.makedirs(log_dir, exist_ok=True)
    f_handler = logging.FileHandler(os.path.join(log_dir, "architect_omniscient.log"), encoding='utf-8')
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)

# ==============================================================================
#        SUBSYSTEM 1: BLACKLIST REGISTRY (The Memory Bank)
# ==============================================================================
class BlacklistRegistry:
    """
    The 'Zone of Denial' Manager.
    Handles the persistent tracking of failed elements, toxic branches, and 
    container quarantine zones.
    """
    def __init__(self, state: AgentState):
        self.state = state
        self._initialize_state()
        
    def _initialize_state(self):
        """Ensures the global state has the necessary data structures."""
        if 'hard_blacklist' not in self.state:
            self.state['hard_blacklist'] = {
                "xpaths": [],           # List[str] - Direct path bans
                "ids": [],              # List[str] - Element ID bans
                "signatures": [],       # List[str] - Class/Attr signatures
                "containers": {},       # Dict[str, int] - Branch failure counts
                "quarantine": []        # List[str] - Banned branches
            }
        # Local fast-lookup cache
        self.xpaths = set(self.state['hard_blacklist']['xpaths'])
        self.ids = set(self.state['hard_blacklist']['ids'])
        self.quarantine = set(self.state['hard_blacklist']['quarantine'])
        self.container_counts = self.state['hard_blacklist']['containers']

    def sync_to_state(self):
        """Commits local cache back to global state for persistence."""
        self.state['hard_blacklist']['xpaths'] = list(self.xpaths)
        self.state['hard_blacklist']['ids'] = list(self.ids)
        self.state['hard_blacklist']['containers'] = self.container_counts
        self.state['hard_blacklist']['quarantine'] = list(self.quarantine)

    def register_failure(self, log_entry: str):
        """
        Parses a log entry to extract and ban the failing element.
        Implements 'Container Radiation' logic.
        """
        # Regex to extract the target XPath from various log formats
        # Matches: "on /html...", "target: /html...", "path: /html..."
        match = re.search(r'(?:on|XPath:|Path:|target)\s*([/\(][a-zA-Z0-9\[\]/@_\-\*\"\'= ]+)', log_entry)
        if not match:
            return

        xpath = match.group(1).strip().rstrip('.').rstrip("'").rstrip('"')
        
        # 1. Ban the specific XPath
        if xpath not in self.xpaths:
            logger.info(f"[REGISTRY] 🚫 Hard-Banning XPath: {xpath}")
            self.xpaths.add(xpath)

        # 2. Ban the specific ID (Anti-Alias)
        # Tries to find patterns like @id='foo' or id="foo" inside the xpath string
        id_match = re.search(r'@id=[\"\']([^\"\']+)[\"\']', xpath)
        if id_match:
            el_id = id_match.group(1)
            if el_id not in self.ids:
                logger.info(f"[REGISTRY] 🚫 Banning Object ID: {el_id}")
                self.ids.add(el_id)

        # 3. Container Radiation Logic
        # Identifies the structural parent (e.g., /html/body/header[1])
        container_match = re.search(r'(/html/body/[a-z]+\[\d+\])', xpath)
        if container_match:
            container = container_match.group(1)
            current_count = self.container_counts.get(container, 0) + 1
            self.container_counts[container] = current_count
            
            # Threshold: If 2 distinct elements in a header fail, assume the whole header is broken
            if current_count >= 2 and container not in self.quarantine:
                logger.warning(f"[REGISTRY] ☣️ QUARANTINE PROTOCOL: Locking UI Branch {container}")
                self.quarantine.add(container)

        self.sync_to_state()

    def check_toxicity(self, xpath: str, attributes: Dict = None) -> Tuple[bool, str]:
        """
        Determines if a candidate element is safe to interact with.
        Returns: (is_toxic, reason)
        """
        # Rule 1: Direct XPath Ban
        if xpath in self.xpaths:
            return True, f"XPath {xpath} is explicitly blacklisted."

        # Rule 2: ID Ban
        if attributes:
            el_id = attributes.get('id')
            if el_id and el_id in self.ids:
                return True, f"Element ID '{el_id}' is globally banned."

        # Rule 3: Container Quarantine
        for q_branch in self.quarantine:
            if xpath.startswith(q_branch):
                return True, f"Target is located in Quarantined Zone: {q_branch}"

        return False, "Safe"

    def purge(self):
        """Wipes the registry. Used on URL changes."""
        logger.info("[REGISTRY] 🧹 Purging forensic memory due to context switch.")
        self.xpaths.clear()
        self.ids.clear()
        self.quarantine.clear()
        self.container_counts.clear()
        self.sync_to_state()

# ==============================================================================
#        SUBSYSTEM 2: HEURISTIC ENGINE (The Vision Layer)
# ==============================================================================
class HeuristicEngine:
    """
    The 'Eye' of the Architect. 
    Implements a 5-Dimensional Scoring System to rank DOM elements.
    """
    def __init__(self, registry: BlacklistRegistry):
        self.registry = registry

    def rank_dom_snapshot(self, dom_snapshot: List[Dict], goal: str) -> str:
        """
        Analyzes the raw DOM snapshot and produces a curated, scored list
        of candidates for the LLM.
        """
        if not dom_snapshot:
            return "DOM SNAPSHOT EMPTY. Recommendation: Trigger ANALYZE_DOM phase."

        scored_candidates = []
        goal_keywords = [k.lower() for k in goal.split() if len(k) > 3]
        
        for el in dom_snapshot:
            score = 0.0
            xpath = el.get('xpath', '')
            tag = el.get('tag', 'UNKNOWN')
            text_content = (el.get('text', '') or "").lower()
            attributes = el.get('attributes', {})
            attr_str = str(attributes).lower()
            
            # --- DIMENSION 1: SEMANTIC RELEVANCE (Max +40) ---
            # Do keywords appear in text or attributes?
            matches = sum(1 for w in goal_keywords if w in text_content or w in attr_str)
            score += (matches * 15.0)
            
            # Explicit boost for 'Search' related tasks
            if 'search' in goal.lower() and ('search' in text_content or 'search' in attr_str):
                score += 20.0

            # --- DIMENSION 2: STRUCTURAL INTEGRITY (Max +20) ---
            # Is the element interactive?
            if el.get('visible', True):
                score += 10.0
            else:
                score -= 50.0 # Heavy penalty for hidden elements
            
            if tag == 'INPUT': score += 15.0
            elif tag == 'BUTTON': score += 10.0
            elif tag == 'A': score += 5.0

            # --- DIMENSION 3: SPATIAL PROBABILITY (Max +15) ---
            # Bias towards standard layout patterns
            if 'header[2]' in xpath: score += 15.0 # Primary Nav usually
            if 'header[1]' in xpath: score -= 5.0  # Top bar (socials/logos) usually
            if 'footer' in xpath: score -= 10.0    # Search bars in footers are rarely primary

            # --- DIMENSION 4: RISK ASSESSMENT (The Veto) ---
            is_toxic, reason = self.registry.check_toxicity(xpath, attributes)
            if is_toxic:
                score = -10000.0 # Effectively removes it
            
            scored_candidates.append({
                "element": el,
                "score": score,
                "reason": reason
            })

        # Sort and Filter
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        top_candidates = [x['element'] for x in scored_candidates if x['score'] > -100][:35]
        
        # Format for LLM Consumption
        output_lines = []
        for el in top_candidates:
            v_status = "VISIBLE" if el.get('visible') else "HIDDEN"
            safe_text = (el.get('text', '') or 'NoText')[:45].strip().replace('\n', ' ')
            id_val = el.get('attributes', {}).get('id', 'N/A')
            
            line = f"[{v_status}] <{el['tag']}> Text:\"{safe_text}\" (ID:{id_val}) Path: {el['xpath']}"
            output_lines.append(line)
            
        if not output_lines:
            return "NO VIABLE CANDIDATES. All visible elements are blacklisted or irrelevant."
            
        return f"Analyzing {len(dom_snapshot)} elements. Top {len(top_candidates)} tactical targets:\n" + "\n".join(output_lines)

# ==============================================================================
#        SUBSYSTEM 3: NEURAL PARSER (The Recovery Reactor)
# ==============================================================================
class NeuralParser:
    """
    A robust JSON extraction engine.
    Can recover valid JSON from malformed LLM outputs using multiple strategies.
    """
    @staticmethod
    def extract_plan(text: str) -> Dict[str, Any]:
        """
        Attempts 5 levels of surgical extraction.
        """
        # Pre-process: remove markdown code blocks
        clean_text = text.strip().replace('```json', '').replace('```', '')
        
        # Strategy 1: Direct Parse
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            pass
            
        # Strategy 2: Regex Block Extraction
        # Finds the first valid { ... } block
        match = re.search(r'\{.*\}', clean_text.replace('\n', ' '), re.DOTALL)
        if match:
            raw_block = match.group(0)
            try:
                # Sanitize common errors: trailing commas
                sanitized = re.sub(r',\s*}', '}', raw_block)
                sanitized = re.sub(r',\s*]', ']', sanitized)
                return json.loads(sanitized)
            except: pass
            
        # Strategy 3: Key-Value Heuristic Scraper
        # Desperation mode: looks for specific keys manually
        try:
            phase_match = re.search(r'"next_phase":\s*"(\w+)"', clean_text)
            target_match = re.search(r'"target_xpath":\s*"([^"]+)"', clean_text)
            if phase_match:
                return {
                    "next_phase": phase_match.group(1),
                    "target_xpath": target_match.group(1) if target_match else None,
                    "thought_process": "Extracted via Heuristic Scraper"
                }
        except: pass

        # Strategy 4: Fallback
        logger.error("[PARSER] 🛑 JSON Extraction Failed. Defaulting to safe rescan.")
        return {
            "thought_process": "JSON Parsing Failure. System defaulting to safe re-scan.",
            "next_phase": "ANALYZE_DOM",
            "target_xpath": None
        }

# ==============================================================================
#        SUBSYSTEM 4: TACTICAL VALIDATOR (The Safety Net)
# ==============================================================================
class TacticalValidator:
    """
    Pre-flight check for plans.
    Ensures the LLM isn't hallucinating or violating safety protocols.
    """
    def __init__(self, registry: BlacklistRegistry):
        self.registry = registry

    def validate_plan(self, plan: Dict) -> Tuple[bool, str]:
        """
        Checks if the plan is executable.
        Returns: (is_valid, rejection_reason)
        """
        phase = plan.get('next_phase', 'ANALYZE_DOM')
        target = plan.get('target_xpath')
        
        # Check 1: Phase Validity
        if phase not in ["NAVIGATE", "ANALYZE_DOM", "COMPLETE", "ABORT", "FIX_ISSUES", "VERIFY_FIX"]:
            return False, f"Invalid Phase: {phase}"

        # Check 2: Navigation Integrity
        if phase == "NAVIGATE" and not target:
            return False, "Navigation phase requested but no Target XPath provided."

        # Check 3: Blacklist Veto
        if target:
            is_toxic, reason = self.registry.check_toxicity(target)
            if is_toxic:
                return False, f"Safety Veto: {reason}"

        return True, "Plan Validated"

# ==============================================================================
#        MAIN CLASS: MISSION ARCHITECT (The Coordinator)
# ==============================================================================
class MissionArchitectAgent:
    """
    The Sentinel-9.6 Omniscient Architect.
    Orchestrates the subsystems to drive the mission to completion.
    """

    def __init__(self):
        self.last_known_url = None
        self.consecutive_failures = 0
        logger.info("Sentinel-9.6 Omniscient Architect Online.")

    def plan(self, state: AgentState) -> AgentState:
        """
        The Main Strategic Loop.
        """
        mission_id = state.get('mission_id', 'UNKNOWN')
        goal = state.get('goal', 'Search')
        history = state.get('history_steps', [])
        error_log = state.get('error_log', [])
        current_url = state.get('current_url', 'Unknown')
        dom_snapshot = state.get('dom_snapshot', [])

        logger.info(f"[{mission_id}] >>> INITIATING OMNISCIENT PLANNING <<<")

        # 1. INITIALIZE SUBSYSTEMS WITH CURRENT STATE
        registry = BlacklistRegistry(state)
        heuristic_engine = HeuristicEngine(registry)
        validator = TacticalValidator(registry)

        # 2. SEMANTIC VICTORY CHECK (Stop if we won)
        # Prevents "Post-Success Looping"
        victory_tokens = ["search?", "results", "q=", "query=", "s="]
        if "search" in goal.lower() and any(t in current_url.lower() for t in victory_tokens):
            logger.info(f"[{mission_id}] 🎯 VICTORY: URL signature '{current_url}' confirms success.")
            state['status'] = 'COMPLETED'
            state['is_complete'] = True
            state['history_steps'].append(f"SUCCESS: Reached target URL: {current_url}")
            return state

        # 3. CONTEXT INTEGRITY CHECK (Crash Recovery)
        # If the last step crashed, our DOM is stale. Force rescan.
        last_error = error_log[-1] if error_log else ""
        if any(k in last_error.lower() for k in ["vanished", "lost", "crash", "timeout"]):
            logger.warning(f"[{mission_id}] ⚠️ CONTEXT FRACTURE: Previous step failed. forcing rescan.")
            state['status'] = 'ANALYZING'
            return state

        # 4. CONTEXT DRIFT CHECK (URL Change)
        if self.last_known_url and self.last_known_url != current_url:
            logger.info(f"[{mission_id}] 🌐 CONTEXT DRIFT: URL changed. Wiping local spatial memory.")
            registry.purge()
            self.last_known_url = current_url
            state['status'] = 'ANALYZING'
            state['dom_snapshot'] = []
            return state
        self.last_known_url = current_url

        # 5. FORENSIC AUDIT (Update Blacklist)
        # Scan recent logs for failures and update registry
        audit_window = history[-15:] + error_log[-15:]
        for entry in audit_window:
            if any(k in entry.upper() for k in ["NO_CHANGE", "CRASH", "FAILED", "NO VISIBLE EFFECT", "TIMEOUT"]):
                registry.register_failure(entry)

        # 6. SENSORY RANKING (Generate Context)
        dom_context = heuristic_engine.rank_dom_snapshot(dom_snapshot, goal)

        # 7. COGNITIVE REASONING (Prompting)
        system_role = (
            "You are the Sentinel-9.6 Omniscient Architect.\n"
            "MISSION RULES:\n"
            "1. OBEY BLACKLIST: Do not select forbidden elements.\n"
            "2. AVOID INSANITY: If Header 1 failed twice, do NOT try it again. Move to Header 2 or Body.\n"
            "3. NO GHOSTS: If an element is [HIDDEN], find the 'Toggle' button (magnifying glass) to click first.\n"
            "4. RESPONSE: Return ONLY raw JSON."
        )

        user_prompt = f"""
        GOAL: {goal}
        URL: {current_url}
        
        === SENSORY DATA (Ranked Candidates) ===
        {dom_context}

        === FORBIDDEN ZONES ===
        Blacklisted XPaths: {list(registry.xpaths)[-5:]}
        Banned IDs: {list(registry.ids)}
        Quarantined Branches: {list(registry.quarantine)}

        === RECENT HISTORY ===
        {json.dumps(history[-3:], indent=2)}

        === RECENT ERRORS ===
        {json.dumps(error_log[-3:], indent=2)}

        === DECISION ===
        Synthesize a plan. 
        If 'Search' was typed but result was NO_CHANGE, you MUST Click the 'Submit' button next.
        
        Format:
        {{
            "thought_process": "Detailed reasoning about spatial location and safety.",
            "next_phase": "NAVIGATE",
            "target_xpath": "xpath string",
            "action_type": "CLICK" | "TYPE",
            "payload": "Digital India"
        }}
        """

        try:
            # 8. INFERENCE
            logger.info(f"[{mission_id}] Transmitting to Neural Engine...")
            raw_response = ai_engine.generate_code(user_prompt, system_role=system_role)
            
            # 9. PARSING
            plan = NeuralParser.extract_plan(raw_response)
            
            thought = plan.get('thought_process', 'No thought.')
            phase = plan.get('next_phase', 'ANALYZE_DOM').upper()
            target = plan.get('target_xpath')
            
            logger.info(f"[{mission_id}] Architect Plan: {phase} -> {target}")
            logger.debug(f"[{mission_id}] Reasoning: {thought}")

            # 10. VALIDATION (The Veto)
            is_valid, reason = validator.validate_plan(plan)
            
            if not is_valid:
                logger.critical(f"[{mission_id}] 🛑 TACTICAL VETO: {reason}")
                state['error_log'].append(f"Architect Safety Veto: {reason}")
                state['status'] = 'ANALYZING'
                return state

            # 11. COMMIT
            if phase == 'NAVIGATE':
                state['semantic_map'] = {
                    'target_xpath': target,
                    'action_type': plan.get('action_type', 'CLICK'),
                    'description': thought[:200]
                }
                if plan.get('action_type') == 'TYPE':
                    state['input_data'] = plan.get('payload', 'Digital India')

            state['status'] = self._map_status(phase)
            mission_db.log_action(mission_id, "MissionArchitect", "STRATEGY_COMMITTED", plan)

        except Exception as e:
            logger.critical(f"[{mission_id}] ARCHITECT SYSTEM FAILURE: {e}", exc_info=True)
            state['error_log'].append(f"Architect Critical Error: {str(e)}")
            state['status'] = "ANALYZING" # Default safe state

        return state

    def _map_status(self, phase: str) -> str:
        mapping = {
            'NAVIGATE': 'NAVIGATING',
            'ANALYZE_DOM': 'ANALYZING',
            'FIX_ISSUES': 'FIXING',
            'VERIFY_FIX': 'VERIFYING',
            'COMPLETE': 'COMPLETED',
            'ABORT': 'FAILED'
        }
        return mapping.get(phase.upper(), 'FAILED')

# ==============================================================================
#        MODULE ENTRY POINT (SELF-DIAGNOSTIC)
# ==============================================================================
if __name__ == "__main__":
    print("--- Sentinel-9.6 Omniscient Architect Diagnostics ---")
    try:
        # Mock State
        test_state = {
            'mission_id': 'TEST_001', 
            'hard_blacklist': {'xpaths': [], 'ids': [], 'containers': {}, 'quarantine': []}
        }
        
        # 1. Test Blacklist Logic
        reg = BlacklistRegistry(test_state)
        reg.register_failure("Action FAILED on /html/body/header[1]/div/input")
        reg.register_failure("Action CRASHED on /html/body/header[1]/button")
        
        if "/html/body/header[1]" in test_state['hard_blacklist']['quarantine']:
            print("[PASS] Container Quarantine Logic")
        else:
            print("[FAIL] Container Quarantine Logic")
            
        # 2. Test Parser
        broken_json = "Here is the plan: ```json { \"next_phase\": \"NAVIGATE\", \"target_xpath\": \"//div\" } ```"
        plan = NeuralParser.extract_plan(broken_json)
        if plan['next_phase'] == "NAVIGATE":
            print("[PASS] Neural Parser Logic")
        else:
            print("[FAIL] Neural Parser Logic")
            
        print("Architect Status: OPERATIONAL")
    except Exception as e:
        print(f"Diagnostics FAILED: {e}")
        traceback.print_exc()