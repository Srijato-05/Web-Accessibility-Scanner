import sys
import os
import json
import logging
import re
from typing import List, Dict, Tuple, Optional

# Path Patching
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.model_loader import ai_engine
from cognition.state_manager import AgentState, mission_db

logger = logging.getLogger("SemanticSensor")

class SemanticSensorAgent:
    """
    AGENT ROLE: The Eyes
    OBJECTIVE: Locate UI elements using Hybrid Search (Vector + Keyword).
    """
    
    def __init__(self):
        self.base_threshold = 0.40
        self.keyword_boost = 0.20  # Boost score if exact keyword match found

    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip().lower()

    def analyze(self, state: AgentState) -> AgentState:
        mission_id = state['mission_id']
        goal = state['goal']
        dom_elements = state.get('dom_snapshot', [])
        
        logger.info(f"[{mission_id}] Sensor: Analyzing {len(dom_elements)} elements for '{goal}'")

        if not dom_elements:
            state['error_log'].append("Sensor Error: DOM Snapshot is empty.")
            state['status'] = "FAILED"
            return state

        # 1. PRE-FILTERING (Optimization)
        # Filter out hidden or empty elements to reduce inference load
        valid_elements = [
            el for el in dom_elements 
            if el.get('text') or el.get('attributes', {}).get('aria_label') or el.get('attributes', {}).get('placeholder')
        ]
        
        if not valid_elements:
            state['error_log'].append("Sensor Error: No actionable elements found.")
            return state

        # 2. HYBRID ENCODING
        # Create a rich text representation for each element
        element_texts = []
        for el in valid_elements:
            raw_text = el.get('text', '')
            aria = el.get('attributes', {}).get('aria_label', '')
            role = el.get('attributes', {}).get('role', '')
            tag = el.get('tag', '')
            # "Sign In button with label 'Login'"
            element_texts.append(f"{raw_text} {aria} {role} {tag}".strip())

        # 3. VECTOR SEARCH
        goal_embedding = ai_engine.get_embedding(goal)
        element_embeddings = ai_engine.get_embedding(element_texts)
        scores = ai_engine.compute_similarity(goal_embedding, element_embeddings)[0]

        # 4. KEYWORD BOOSTING (The Hybrid Logic)
        goal_keywords = set(self._normalize_text(goal).split())
        adjusted_scores = []
        
        for idx, score in enumerate(scores):
            current_score = float(score)
            el_text_norm = self._normalize_text(element_texts[idx])
            
            # Boost if exact keyword match (e.g., "Login" in "Login Button")
            matches = sum(1 for kw in goal_keywords if kw in el_text_norm)
            if matches > 0:
                current_score += (matches * 0.05) # Small boost per keyword
                
            adjusted_scores.append(current_score)

        # 5. RANKING & SELECTION
        best_match_idx = adjusted_scores.index(max(adjusted_scores))
        best_score = adjusted_scores[best_match_idx]
        best_element = valid_elements[best_match_idx]

        # 6. LOGGING & DECISION
        if best_score >= self.base_threshold:
            log_msg = f"Found target: {best_element.get('xpath')} (Score: {best_score:.2f})"
            mission_db.log_action(mission_id, "SemanticSensor", "LOCATED_TARGET", log_msg)
            
            state['history_steps'].append(f"Sensor Found: {best_element.get('text')} ({best_score:.2f})")
            
            # Inject Target for Navigator
            state['semantic_map'] = {
                "target_xpath": best_element.get('xpath'),
                "target_desc": best_element.get('text'),
                "confidence": best_score,
                "action_type": "CLICK" if best_element.get('tag') in ['a', 'button'] else "TYPE"
            }
            state['status'] = "NAVIGATING"
        else:
            state['error_log'].append(f"Sensor Failed: Best match '{best_element.get('text')}' ({best_score:.2f}) too low.")
            state['status'] = "FAILED"

        return state