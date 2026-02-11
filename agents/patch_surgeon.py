import sys
import os
import logging
from typing import List, Dict, Optional, Any

# Path Patching
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.model_loader import ai_engine
from cognition.state_manager import AgentState, mission_db

logger = logging.getLogger("PatchSurgeon")

class PatchSurgeonAgent:
    """
    AGENT ROLE: The Fixer
    OBJECTIVE: Generate Remediation Code using LLM + Heuristics.
    """

    def heal(self, state: AgentState) -> AgentState:
        mission_id = state['mission_id']
        violations = state.get('detected_violations', [])
        
        if not violations:
            logger.info("Surgeon: No violations to fix.")
            return state

        fixes = []
        logger.info(f"[{mission_id}] Surgeon: Attempting to fix {len(violations)} issues.")

        for violation in violations:
            v_id = violation.get('id')
            v_xpath = violation.get('xpath')
            
            # --- STRATEGY 1: HEURISTIC FIXER (Math-Based) ---
            if "color-contrast" in v_id:
                heuristic_fix = self._heuristic_contrast_fix(violation)
                if heuristic_fix:
                    fixes.append(heuristic_fix)
                    mission_db.log_action(mission_id, "PatchSurgeon", "HEURISTIC_FIX", f"Fixed contrast for {v_xpath}")
                    continue

            # --- STRATEGY 2: GENERATIVE FIXER (AI-Based) ---
            visual_context = "No image available."
            if "image" in v_id or "alt" in v_id:
                 if state.get('screenshot_path'):
                     visual_context = ai_engine.analyze_image(
                         state['screenshot_path'], 
                         f"Describe the icon/image at this location: {v_xpath}"
                     )

            prompt = (
                f"Generate a vanilla JavaScript snippet to fix this accessibility violation.\n"
                f"Violation: {v_id}\n"
                f"Element: {v_xpath}\n"
                f"Context: {visual_context}\n"
                f"Requirements: Use document.evaluate() to find element. Add try/catch block."
            )
            
            fix_code = ai_engine.generate_code(prompt)
            
            if "Error" not in fix_code:
                fixes.append({
                    "violation_id": v_id,
                    "xpath": v_xpath,
                    "fix_code": fix_code,
                    "type": "AI_GENERATED"
                })
                mission_db.log_action(mission_id, "PatchSurgeon", "AI_FIX", f"Generated JS for {v_id}")

        state['proposed_fixes'] = fixes
        state['status'] = "VERIFYING" 
        
        return state

    def _heuristic_contrast_fix(self, violation: dict) -> Optional[dict]:
        """
        Mathematically calculates the nearest WCAG-compliant color.
        """
        xpath = violation.get('xpath')
        
        # JS to force high contrast (Black on White or White on Black)
        fix_code = f"""
        try {{
            let el = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (el) {{
                el.style.color = "#000000";
                el.style.backgroundColor = "#FFFFFF";
                el.style.border = "2px solid #000000";
                console.log("Drishti-AX: Applied Heuristic Contrast Fix");
            }}
        }} catch(e) {{}}
        """
        
        return {
            "violation_id": "color-contrast",
            "xpath": xpath,
            "fix_code": fix_code,
            "type": "HEURISTIC"
        }