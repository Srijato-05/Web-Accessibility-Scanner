import sys
import os
import logging
import asyncio
from playwright.async_api import async_playwright
from axe_core_python.async_playwright import Axe

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cognition.state_manager import AgentState, mission_db
from src.utils.helpers import calculate_drishti_score

logger = logging.getLogger("QualityWarden")

class QualityWardenAgent:
    """
    AGENT ROLE: The Judge
    OBJECTIVE: Differential Verification (Before vs After).
    """

    async def verify_fixes(self, state: AgentState) -> AgentState:
        mission_id = state['mission_id']
        fixes = state.get('proposed_fixes', [])
        target_url = state['target_url']

        if not fixes:
            logger.info("Warden: No fixes to verify.")
            state['status'] = "COMPLETED"
            return state

        logger.info(f"[{mission_id}] Warden: Starting Differential Audit...")

        async with async_playwright() as p:
            # Launch in Headless mode for speed
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 1. BASELINE AUDIT (Control Group)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                axe = Axe()
                results_pre = await axe.run(page)
                score_pre = self._get_simple_score(results_pre)
                logger.info(f"Baseline Score: {score_pre}")

                # 2. INJECT PATCHES (Experimental Group)
                successful_injections = 0
                for fix in fixes:
                    code = fix.get('fix_code', '')
                    if code:
                        try:
                            # IIFE Injection
                            await page.evaluate(f"(function(){{ {code} }})();")
                            successful_injections += 1
                        except Exception as e:
                            logger.error(f"Injection Failed for {fix.get('violation_id')}: {e}")

                # 3. VERIFICATION AUDIT
                results_post = await axe.run(page)
                score_post = self._get_simple_score(results_post)
                
                # 4. DIFFERENTIAL ANALYSIS
                score_delta = score_post - score_pre
                logger.info(f"Post-Fix Score: {score_post} (Delta: {score_delta:+d})")

                # 5. REGRESSION CHECK
                # Did we accidentally break valid elements?
                # (Simple check: Did violations count increase in any category?)
                # [Advanced logic omitted for brevity, focusing on score delta]

                if score_delta > 0:
                    state['status'] = "COMPLETED"
                    state['verification_score'] = score_post
                    mission_db.log_action(mission_id, "QualityWarden", "VERIFIED_SUCCESS", f"Improvement: +{score_delta}")
                    mission_db.complete_mission(mission_id, score_post, "SUCCESS")
                else:
                    state['status'] = "FAILED"
                    mission_db.log_action(mission_id, "QualityWarden", "VERIFIED_FAIL", "No score improvement.")
                    mission_db.complete_mission(mission_id, score_post, "FAILED_NO_IMPROVEMENT")

            except Exception as e:
                logger.error(f"Warden Crash: {e}")
                state['status'] = "FAILED"
            
            finally:
                await browser.close()

        return state

    def _get_simple_score(self, axe_results):
        # Quick calculation reusing the Phase 1 logic wrapper
        return calculate_drishti_score(
            axe_results.get("violations", []), 
            0, 0, False, True, 0, False, False
        )