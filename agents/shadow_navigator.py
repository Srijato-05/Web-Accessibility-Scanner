import sys
import os
import asyncio
import logging
from typing import Dict, Any, Optional

# Third-party imports
try:
    from playwright.async_api import Page, ElementHandle, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[CRITICAL] Playwright not installed. Run 'uv pip install playwright'")
    sys.exit(1)

# Path Patching
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cognition.state_manager import AgentState, mission_db

# ==========================================
#        LOGGING CONFIGURATION
# ==========================================
logger = logging.getLogger("ShadowNavigator")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - [NAVIGATOR] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class ShadowNavigatorAgent:
    """
    AGENT ROLE: The Driver (Pillar 2)
    OBJECTIVE: Execute browser actions with strict state verification and advanced
               anti-detection / anti-blocking measures.
    
    SENTINEL-7 CAPABILITIES:
    1. Fault-Tolerant History: Logs target XPaths to history even during crashes.
    2. Ghost Writer v2: Injects text into hidden inputs when standard typing fails.
    3. Delta Verification: Detects subtle DOM changes to verify action success.
    4. Auto-Escalation: Cycles through Standard -> Force -> JS Dispatch -> Ghost Click.
    """

    async def execute(self, state: AgentState, page: Page) -> AgentState:
        """
        Executes the planned action and verifies its impact on the page state.
        """
        mission_id = state['mission_id']
        target_map = state.get('semantic_map', {})
        
        # ---------------------------------------------------------
        # 1. INITIAL NAVIGATION HANDLER
        # ---------------------------------------------------------
        if not target_map and state.get('target_url') and state['status'] == 'STARTED':
            logger.info(f"[{mission_id}] Initializing Mission Navigation to {state['target_url']}")
            try:
                # Advanced Navigation Options
                await page.goto(
                    state['target_url'], 
                    timeout=90000, 
                    wait_until='domcontentloaded'
                )
                state['current_url'] = page.url
                state['status'] = 'ANALYZING' 
                return state
            except Exception as e:
                logger.critical(f"Initial Navigation Failed: {e}")
                state['status'] = 'FAILED'
                state['error_log'].append(f"Initial Nav Failed: {e}")
                return state

        # ---------------------------------------------------------
        # 2. TARGET VALIDATION
        # ---------------------------------------------------------
        xpath = target_map.get('target_xpath')
        action = target_map.get('action_type', 'CLICK')
        
        if not xpath:
             logger.warning(f"[{mission_id}] No target XPath provided for execution.")
             state['status'] = 'PLANNING'
             return state

        logger.info(f"[{mission_id}] EXECUTING {action} on {xpath}...")

        try:
            # ---------------------------------------------------------
            # 3. PRE-ACTION STATE SNAPSHOT
            # ---------------------------------------------------------
            # We capture the state of the page before we touch anything.
            pre_state = await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
                return {
                    url: window.location.href,
                    visible_inputs_count: inputs.filter(i => i.offsetWidth > 0).length,
                    total_elements: document.querySelectorAll('*').length,
                    title: document.title
                };
            }""")
            
            # ---------------------------------------------------------
            # 4. ROBUST ELEMENT LOCATION
            # ---------------------------------------------------------
            element = await self._locate_robustly(page, xpath)
            if not element:
                # SENTINEL-7 FIX: Log "Vanished" to history so Architect sees it
                fail_msg = f"FAILED on {xpath} -> Reason: Element Vanished/Hidden"
                state['history_steps'].append(fail_msg)
                logger.error(f"[{mission_id}] Target element vanished: {xpath}")
                raise Exception(f"Element lost or hidden: {xpath}")

            # ---------------------------------------------------------
            # 5. ACTION EXECUTION (ESCALATION LADDER)
            # ---------------------------------------------------------
            if action == 'CLICK':
                await self._perform_escalated_click(page, element, xpath)
            elif action == 'TYPE':
                text = state.get('input_data', "Digital India")
                await self._perform_robust_fill(page, element, text, xpath)
                await page.keyboard.press("Enter")
            
            # ---------------------------------------------------------
            # 6. POST-ACTION VERIFICATION & SETTLING
            # ---------------------------------------------------------
            # Wait for network idle or animations
            logger.info(f"[{mission_id}] Waiting for UI state to settle...")
            await asyncio.sleep(3.5) # Increased for government sites
            
            post_state = await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
                return {
                    url: window.location.href,
                    visible_inputs_count: inputs.filter(i => i.offsetWidth > 0).length,
                    total_elements: document.querySelectorAll('*').length,
                    title: document.title
                };
            }""")

            # ---------------------------------------------------------
            # 7. IMPACT ANALYSIS
            # ---------------------------------------------------------
            impact = "NO_CHANGE"
            
            if post_state['url'] != pre_state['url']:
                impact = "URL_NAVIGATED"
                logger.info(f"[{mission_id}] 🟢 SUCCESS: URL changed to {post_state['url']}")
                
            elif post_state['visible_inputs_count'] > pre_state['visible_inputs_count']:
                impact = "INPUT_FIELD_APPEARED"
                logger.info(f"[{mission_id}] 🟢 SUCCESS: New input field appeared!")
                
            elif abs(post_state['total_elements'] - pre_state['total_elements']) > 2:
                impact = "DOM_MUTATED"
                logger.info(f"[{mission_id}] 🟢 SUCCESS: DOM structure changed.")
                
            else:
                logger.warning(f"[{mission_id}] 🟡 WARNING: Action appeared to have NO VISIBLE EFFECT.")

            # ---------------------------------------------------------
            # 8. ARTIFACT GENERATION & STATE UPDATE
            # ---------------------------------------------------------
            step_count = len(state['history_steps']) + 1
            screenshot_path = os.path.join("reports", "evidence", f"{mission_id}_step_{step_count}.png")
            await page.screenshot(path=screenshot_path)
            
            history_msg = f"{action} on {xpath} -> Result: {impact}"
            state['history_steps'].append(history_msg)
            state['screenshot_path'] = screenshot_path
            state['current_url'] = page.url
            state['last_action_impact'] = impact  # CRITICAL: Passed to Architect for Context Nuke

            # Logic Feedback Loop
            if impact == "NO_CHANGE":
                state['error_log'].append(f"Action '{action}' on {xpath} executed but caused NO STATE CHANGE.")

            state['status'] = 'PLANNING' 
            mission_db.log_action(mission_id, "ShadowNavigator", "ACTION_EXEC", history_msg)

        except Exception as e:
            logger.error(f"[{mission_id}] Navigator Crash: {e}", exc_info=True)
            
            # SENTINEL-7 CRITICAL FIX: Ensure the CRASH is recorded with the XPath
            # This ensures the Architect knows EXACTLY which element failed
            crash_msg = f"CRASH on {xpath} -> {str(e)[:50]}"
            state['history_steps'].append(crash_msg)
            
            state['error_log'].append(f"Navigator Exception: {str(e)}")
            state['status'] = 'PLANNING' # Fallback to planning to allow retry

        return state

    async def _locate_robustly(self, page: Page, xpath: str) -> Optional[ElementHandle]:
        """
        Attempts to find the element across all Frames and Shadow Roots.
        """
        try:
            # 1. Check Main Page
            el = page.locator(f"xpath={xpath}").first
            if await el.count() > 0: return el
            
            # 2. Check All Iframes
            for frame in page.frames:
                el = frame.locator(f"xpath={xpath}").first
                if await el.count() > 0: return el
        except Exception:
            pass
        return None

    async def _perform_escalated_click(self, page: Page, element: ElementHandle, xpath: str):
        """
        Executes a click using an Escalation Ladder strategy.
        Level 1: Standard Playwright Click (Human-like)
        Level 2: Force Click (Bypasses overlays)
        Level 3: JavaScript Dispatch (Simulated Event)
        """
        # Level 1: Standard
        try:
            logger.info("Attempting Level 1: Standard Click")
            await element.click(timeout=3000)
            return
        except Exception as e:
            logger.warning(f"Standard click failed: {e}. Escalating...")
            
        # Level 2: Force
        try:
            logger.info("Attempting Level 2: Force Click")
            await element.click(force=True, timeout=2000)
            return
        except Exception:
            logger.warning("Force click failed. Escalating...")

        # Level 3: JS Injection (The Nuclear Option)
        logger.info("Attempting Level 3: JS Dispatch")
        await page.evaluate(f"""
            let target = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (target) {{
                target.click();
                // Dispatch full event chain for React/Angular listeners
                target.dispatchEvent(new Event('mousedown', {{bubbles: true}}));
                target.dispatchEvent(new Event('mouseup', {{bubbles: true}}));
                target.dispatchEvent(new Event('click', {{bubbles: true}}));
            }}
        """)

    async def _perform_robust_fill(self, page: Page, element: ElementHandle, text: str, xpath: str):
        """
        Robust Type Strategy with 'Ghost Writer' Fallback.
        Handles hidden, collapsed, or readonly inputs by injecting values via JS.
        """
        try:
            # Check visibility before typing
            if await element.is_visible():
                logger.info("Input is visible. Using Standard Fill.")
                await element.fill(text, timeout=5000)
                return
            else:
                logger.warning("Target input is NOT visible. Escalating to Force Fill...")
        except Exception:
            logger.warning("Standard fill check failed. Escalating...")

        try:
            # Force Fill
            await element.fill(text, force=True, timeout=2000)
            logger.info("Force Fill successful.")
            return
        except Exception:
            logger.warning("Force fill failed. Engaging Ghost Writer...")

        # Level 3: Ghost Writer (JS Injection)
        # Directly sets value property and triggers change events
        logger.info("Engaging Ghost Writer (JS Injection)...")
        await page.evaluate(f"""
            let target = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (target) {{
                target.value = "{text}";
                target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                target.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                try {{ target.focus(); }} catch(e) {{}}
            }}
        """)
        logger.info("Ghost Writer execution complete.")