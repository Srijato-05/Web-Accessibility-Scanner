import sys
import os
import json
import logging
import re
import math
from typing import Dict, Any, List, Optional, Tuple, Union

# ==========================================
#        ENVIRONMENT & IMPORTS
# ==========================================
# Ensure the system path includes the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.utils.model_loader import ai_engine
    from cognition.state_manager import AgentState, mission_db
except ImportError as e:
    # Critical failure if core modules are missing
    print(f"[CRITICAL] Architect Import Error: {e}")
    sys.exit(1)

# ==========================================
#        LOGGING CONFIGURATION
# ==========================================
logger = logging.getLogger("MissionArchitect")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - [ARCHITECT] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ==========================================
#        THE MISSION ARCHITECT AGENT
# ==========================================
class MissionArchitectAgent:
    """
    AGENT ROLE: The Strategist (Pillar 2)
    OBJECTIVE: Decompose high-level goals into atomic actions, handle UI state logic,
               and recover from execution failures using Metacognition.
    
    SENTINEL-7 ADVANCED CAPABILITIES:
    1. Cross-Reference Blacklisting: Scans both history AND error logs to identify failing elements.
    2. Context Drift Recovery: Detects URL changes and element "vanishing" to force re-analysis.
    3. Spatial Prioritization: Scores elements in main content areas higher than persistent headers.
    4. Recursive JSON Repair: Self-heals broken LLM responses using multi-stage regex.
    """

    def __init__(self):
        self.max_retries = 3
        self.last_known_url = None
        self.xpath_blacklist = set()
        
        # Valid State Transitions for the State Machine
        self.valid_phases = [
            "NAVIGATE",     # Move to a URL or Click an element
            "ANALYZE_DOM",  # Scan the page for elements (Perception)
            "FIX_ISSUES",   # Generate code patches (Remediation)
            "VERIFY_FIX",   # Run validation scans (Quality Assurance)
            "COMPLETE",     # Success condition met
            "ABORT"         # Irrecoverable failure
        ]

    def plan(self, state: AgentState) -> AgentState:
        """
        Main execution method.
        Analyzes the current state, history, and goal to determine the optimal next move.
        """
        mission_id = state['mission_id']
        goal = state['goal']
        history = state.get('history_steps', [])
        error_log = state.get('error_log', [])
        current_url = state.get('current_url', 'Unknown')
        
        logger.info(f"[{mission_id}] Architect: Synthesizing strategy for '{goal}'...")

        # ---------------------------------------------------------
        # 1. SENTINEL-7: CONTEXT DRIFT & CRASH DETECTION
        # ---------------------------------------------------------
        # Check 1: Did the last action cause a crash/vanish?
        if error_log and ("vanished" in error_log[-1].lower() or "crash" in error_log[-1].lower()):
            logger.warning(f"[{mission_id}] ⚠️ Target vanished/crashed in previous step. Forcing re-analysis to update DOM.")
            state['status'] = 'ANALYZING'
            return state

        # Check 2: Did the URL change?
        if self.last_known_url and self.last_known_url != current_url:
            logger.warning(f"[{mission_id}] ⚠️ Context Drift Detected! URL changed from {self.last_known_url} to {current_url}.")
            logger.info(f"[{mission_id}] Initiating CONTEXT NUKE protocol: Wiping DOM memory and forcing analysis.")
            
            # Reset internal state tracking
            self.last_known_url = current_url
            self.xpath_blacklist.clear()
            
            # Force State Transition
            state['status'] = 'ANALYZING'
            state['dom_snapshot'] = [] # Clear old snapshot
            return state
        
        self.last_known_url = current_url

        # ---------------------------------------------------------
        # 2. ADVANCED BLACKLISTING (LOOP BREAKER)
        # ---------------------------------------------------------
        # We combine history AND errors to find bad XPaths.
        # This fixes the "Ghost Blacklist" bug where crashes weren't being tracked.
        combined_logs = history + error_log
        
        for entry in combined_logs[-15:]: # Look back further
            # Regex to find any mentioned XPath
            match = re.search(r'(?:on|hidden:)\s*(/[^ ]+)', entry)
            if match:
                failed_xpath = match.group(1).strip()
                # If "FAILED", "CRASH", "NO_CHANGE", or "hidden" is in the line
                if any(k in entry.upper() for k in ["FAILED", "CRASH", "NO_CHANGE", "NO VISIBLE EFFECT", "HIDDEN"]):
                    if failed_xpath not in self.xpath_blacklist:
                        logger.info(f"[{mission_id}] 🚫 Blacklisting ineffective XPath: {failed_xpath}")
                        self.xpath_blacklist.add(failed_xpath)

        loop_constraint = ""
        if self.xpath_blacklist:
            loop_constraint = (
                f"CRITICAL CONSTRAINT: You are FORBIDDEN from using these failed XPaths: {list(self.xpath_blacklist)}. "
                "You MUST choose a different element."
            )

        # ---------------------------------------------------------
        # 3. CANDIDATE SCORING & DOM SUMMARY
        # ---------------------------------------------------------
        # Instead of sending raw JSON, we score elements based on relevance to the goal.
        dom_summary = "DOM Snapshot empty. Choose 'ANALYZE_DOM'."
        
        if state.get('dom_snapshot'):
            raw_elements = state['dom_snapshot']
            scored_elements = []
            
            # Scoring Keywords based on Goal
            keywords = goal.lower().split()
            
            for el in raw_elements:
                score = 0
                el_text = (el.get('text', '') + " " + str(el.get('attributes', {}))).lower()
                xpath = el.get('xpath', '')
                
                # Relevance Scoring
                if any(k in el_text for k in keywords): score += 10
                if el.get('visible', True): score += 5
                if el.get('tag') in ['BUTTON', 'A', 'INPUT']: score += 2
                
                # SPATIAL HEURISTIC: Penalize header[1] if it has failed before, prefer header[2]
                if 'header[1]' in xpath and len(self.xpath_blacklist) > 0: score -= 2
                if 'header[2]' in xpath: score += 5 
                
                if xpath in self.xpath_blacklist: score -= 1000 # Hard penalty for blacklisted items
                
                scored_elements.append((score, el))
            
            # Sort by score descending
            scored_elements.sort(key=lambda x: x[0], reverse=True)
            
            # Select Top 35 Candidates
            top_candidates = [x[1] for x in scored_elements[:35]]
            
            # Format for Prompt
            samples = []
            for el in top_candidates:
                visibility = "VISIBLE" if el.get('visible', True) else "HIDDEN"
                tag = el.get('tag', 'UNKNOWN')
                text = el.get('text', '').strip()[:50]
                xpath = el.get('xpath', '')
                attrs = el.get('attributes', {})
                attr_str = f"ID:{attrs.get('id','')} Role:{attrs.get('role','')}"
                
                samples.append(f"[{visibility}] '{text}' ({tag}) {{{attr_str}}} XPath: {xpath}")
            
            dom_summary = f"DOM contains {len(raw_elements)} elements. Showing Top {len(samples)} Candidates:\n" + "\n".join(samples)

        # ---------------------------------------------------------
        # 4. PROMPT ENGINEERING (CHAIN OF THOUGHT)
        # ---------------------------------------------------------
        system_prompt = (
            "You are the Mission Architect for an Autonomous Web Agent (Drishti-AX).\n"
            "Your objective: Achieve the GOAL on a government website.\n"
            "\n"
            "--- RULES OF ENGAGEMENT ---\n"
            "1. UI LOGIC: If an input is marked [HIDDEN], you CANNOT type into it. You must find a toggle button (icon/magnifying glass) to reveal it.\n"
            "2. LOOP AVOIDANCE: Never repeat an action that resulted in 'NO_CHANGE' or 'CRASH'.\n"
            "3. FORMAT: Output STRICT JSON Only. No markdown.\n"
            "\n"
            "--- JSON SCHEMA ---\n"
            "{\n"
            "  'thought_process': 'Step-by-step reasoning about the state and strategy',\n"
            "  'next_phase': 'NAVIGATE' | 'ANALYZE_DOM' | 'COMPLETE',\n"
            "  'target_xpath': 'The exact XPath from the candidates list',\n"
            "  'action_type': 'CLICK' | 'TYPE',\n"
            "  'input_data': 'The text to type (only for TYPE actions)'\n"
            "}"
        )

        user_prompt = f"""
        GOAL: {goal}
        CURRENT URL: {current_url}
        
        === DOM CANDIDATES ===
        {dom_summary}

        === EXECUTION HISTORY (Last 5) ===
        {json.dumps(history[-5:])}

        === SYSTEM ERRORS (Last 3) ===
        {json.dumps(error_log[-3:])}

        === WARNINGS & CONSTRAINTS ===
        {loop_constraint}

        === DECISION ===
        Determine the single next logical phase.
        1. If lost or URL changed -> 'ANALYZE_DOM'
        2. If target hidden -> 'NAVIGATE' to CLICK toggle.
        3. If target visible -> 'NAVIGATE' to TYPE/CLICK target.
        """

        try:
            # ---------------------------------------------------------
            # 5. GENERATIVE REASONING (LLM CALL)
            # ---------------------------------------------------------
            logger.info(f"[{mission_id}] Sending Prompt to AI Engine...")
            response_text = ai_engine.generate_code(user_prompt, system_role=system_prompt)
            
            # ---------------------------------------------------------
            # 6. ROBUST JSON REPAIR & PARSING
            # ---------------------------------------------------------
            plan = self._extract_json_from_response(response_text)
            
            thought = plan.get('thought_process', 'No thought provided.')
            next_phase = plan.get('next_phase', 'ANALYZE_DOM').upper()
            target_xpath = plan.get('target_xpath')
            action_type = plan.get('action_type', 'CLICK')
            input_data = plan.get('input_data', '')

            logger.info(f"[{mission_id}] Architect Thought: {thought}")
            logger.info(f"[{mission_id}] Decision: {next_phase} -> {action_type} on {target_xpath}")

            # ---------------------------------------------------------
            # 7. STATE TRANSITION & VALIDATION
            # ---------------------------------------------------------
            
            # Heuristic Safety Net: Force Analysis if Navigation Fails repeatedly
            if next_phase == 'NAVIGATE' and len(error_log) > 4 and state['status'] == 'FAILED':
                logger.warning(f"[{mission_id}] High error rate detected during Navigation. Forcing Re-Analysis.")
                next_phase = 'ANALYZE_DOM'

            # Validate Phase
            if next_phase not in self.valid_phases:
                logger.error(f"Invalid Phase '{next_phase}'. Defaulting to ANALYZE_DOM.")
                next_phase = 'ANALYZE_DOM'

            # --- CRITICAL: PASS INTENT TO NAVIGATOR ---
            if next_phase == 'NAVIGATE':
                if target_xpath:
                    # Final Check against Blacklist
                    if target_xpath in self.xpath_blacklist:
                        logger.warning(f"[{mission_id}] LLM selected blacklisted XPath. Overriding to ANALYZE_DOM.")
                        next_phase = 'ANALYZE_DOM'
                    else:
                        state['semantic_map'] = {
                            'target_xpath': target_xpath,
                            'action_type': action_type,
                            'description': "Target selected by Architect"
                        }
                        if action_type == 'TYPE':
                            state['input_data'] = input_data if input_data else "Test Data"
                else:
                    logger.warning(f"[{mission_id}] AI chose NAVIGATE but provided no XPath. Switching to ANALYZE_DOM.")
                    next_phase = 'ANALYZE_DOM'

            # Update System Status
            state['status'] = self._map_phase_to_status(next_phase)
            
            # Log Decision to Audit DB
            mission_db.log_action(mission_id, "MissionArchitect", "PLAN_UPDATE", {
                "thought": thought,
                "next": next_phase,
                "target": target_xpath,
                "action": action_type
            })

        except Exception as e:
            logger.error(f"Planning Crash: {e}", exc_info=True)
            state['status'] = "FAILED"
            state['error_log'].append(f"Architect Error: {str(e)}")

        return state

    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Advanced JSON Recovery Engine.
        Attempts multiple strategies to extract valid JSON from LLM chatter.
        """
        # Strategy 1: Clean Parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        # Strategy 2: Code Block Extraction
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
            
        # Strategy 3: Brute Force Regex (First { to last })
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
            
        # Strategy 4: Aggressive String Sanitization (Fixing Common LLM Errors)
        try:
            clean_text = text.replace("```json", "").replace("```", "").strip()
            # Fix trailing commas in objects/arrays
            clean_text = re.sub(r',\s*}', '}', clean_text)
            clean_text = re.sub(r',\s*]', ']', clean_text)
            # Fix unescaped quotes (simple heuristic)
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"JSON Parsing Failed completely. Raw Output: {text[:200]}... Error: {e}")
            return {
                "thought_process": "JSON Parsing Failed. The Architect produced invalid output.",
                "next_phase": "ANALYZE_DOM",
                "strategy": "Fallback"
            }

    def _map_phase_to_status(self, phase):
        m = {
            'NAVIGATE': 'NAVIGATING',
            'ANALYZE_DOM': 'ANALYZING',
            'FIX_ISSUES': 'FIXING',
            'VERIFY_FIX': 'VERIFYING',
            'COMPLETE': 'COMPLETED',
            'ABORT': 'FAILED'
        }
        return m.get(phase.upper(), 'FAILED')