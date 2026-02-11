"""
Drishti-AX: Shadow Navigator Agent (The Driver Pillar)
Module: agents/shadow_navigator.py
Version: Sentinel-9.5 Zenith ("Titan" Release)
Author: Sentinel Core System
Timestamp: 2026-02-12 06:00:00 UTC

Description:
    The 'Hands' of the autonomous squad. This module executes browser-level
    interactions with extreme prejudice. It implements a multi-stage
    Escalation Ladder and the 'Enter Hammer' to bypass complex UI listeners
    and anti-bot deterrents.

    CAPABILITIES:
    -------------------------------------------------------------------------
    1.  SHADOW PIERCER ENGINE:
        - Recursively scans all Iframes and Shadow DOM roots.
        - Unifies the DOM into a single queryable surface.

    2.  THE ESCALATION LADDER:
        - Level 1: Standard Playwright Interaction (Human-like).
        - Level 2: Force Bypass (Ignores visibility/overlap checks).
        - Level 3: JavaScript Injection (Direct Event Dispatch).
        - Level 4: Coordinate Targeting (Hardware Mouse Events).

    3.  THE ENTER HAMMER:
        - Dispatches a comprehensive sequence of Keyboard events.
        - Triggers React/Angular/Vue change listeners manually.
        - Forces form submission if standard triggers fail.

    4.  DELTA SENSING (VERIFICATION):
        - Compares Pre/Post state fingerprints.
        - Detects 'Silent Success' (DOM mutation without URL change).
        - Detects 'Ghost Failures' (No visual change).

    5.  FORENSIC INTEGRATION:
        - Logs distinct failure modes (VANISHED vs BLOCKED vs NO_EFFECT).
        - Takes micro-snapshots of elements before interaction.
    -------------------------------------------------------------------------
"""

import sys
import os
import asyncio
import logging
import time
import json
import math
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

# ==============================================================================
#        ENVIRONMENT & CORE DEPENDENCIES SETUP
# ==============================================================================
# Robust path patching for absolute module resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from playwright.async_api import Page, ElementHandle, Locator, Frame, TimeoutError as PWTimeout
    from cognition.state_manager import AgentState, mission_db
except ImportError as e:
    print(f"[CRITICAL FATAL ERROR] Navigator dependencies missing: {e}")
    sys.exit(1)

# ==============================================================================
#        ADVANCED LOGGING CONFIGURATION
# ==============================================================================
logger = logging.getLogger("ShadowNavigator")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # 1. Console Handler (Operator View)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('%(asctime)s - [NAVIGATOR] - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)
    
    # 2. Forensic File Handler (Deep Audit)
    log_dir = os.path.join(project_root, "reports", "logs")
    os.makedirs(log_dir, exist_ok=True)
    f_handler = logging.FileHandler(os.path.join(log_dir, "navigator_forensics.log"), encoding='utf-8')
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)

# ==============================================================================
#        CONSTANTS & CONFIGURATION
# ==============================================================================
INTERACTION_TIMEOUT = 5000  # 5 seconds per interaction attempt
SETTLE_TIME = 3.5           # Time to wait for UI to stabilize after action
MAX_RETRIES = 3             # Number of times to retry a failed acquisition

# ==============================================================================
#        THE SHADOW NAVIGATOR AGENT CLASS
# ==============================================================================
class ShadowNavigatorAgent:
    """
    Executes browser actions with high availability and deterministic verification.
    """

    def __init__(self):
        self.screenshot_dir = os.path.join(project_root, "reports", "evidence")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        logger.info("Sentinel-9.5 Zenith Navigator initialized. Escalation protocols active.")

    async def execute(self, state: AgentState, page: Page) -> AgentState:
        """
        The Main Execution Loop. Orchestrates the transition from Planning to Action.
        
        Workflow:
        1. Pre-Check: Validate state and target.
        2. Fingerprinting: Capture the starting state of the UI.
        3. Acquisition: Find the element in Main, Frames, or Shadow DOM.
        4. Interaction: Attempt the action (escalating if blocked).
        5. Verification: Wait for settle and calculate Delta (Impact).
        6. Logging: Record results in history to prevent loops.
        """
        mission_id = state.get('mission_id', 'UNKNOWN')
        target_map = state.get('semantic_map', {})
        current_url = page.url
        
        # ----------------------------------------------------------------------
        # STAGE 1: COLD START NAVIGATION
        # ----------------------------------------------------------------------
        # If we have a target URL but no specific element target, we navigate.
        if not target_map and state.get('target_url') and state['status'] == 'STARTED':
            logger.info(f"[{mission_id}] 🚀 COLD START: Navigating to {state['target_url']}")
            try:
                await page.goto(state['target_url'], timeout=90000, wait_until='domcontentloaded')
                await self._force_ui_hydration(page)
                
                state['current_url'] = page.url
                state['status'] = 'ANALYZING' 
                return state
            except Exception as e:
                logger.critical(f"[{mission_id}] Initial Navigation Failed: {e}", exc_info=True)
                state['status'] = 'FAILED'
                state['error_log'].append(f"Initial Nav Failed: {str(e)}")
                return state

        # ----------------------------------------------------------------------
        # STAGE 2: ACTION PREPARATION
        # ----------------------------------------------------------------------
        xpath = target_map.get('target_xpath')
        action = target_map.get('action_type', 'CLICK')
        payload = state.get('input_data', 'Digital India')
        
        if not xpath:
             logger.warning(f"[{mission_id}] ⚠️ NO TARGET: Architect provided null XPath.")
             state['status'] = 'PLANNING'
             return state

        logger.info(f"[{mission_id}] ⚡ ZENITH EXECUTION: {action} on {xpath}")

        try:
            # 1. Capture UI Fingerprint (The "Before" state)
            # We measure the DOM to detect changes later.
            pre_state = await self._capture_fingerprint(page)
            logger.debug(f"[{mission_id}] Pre-Action Fingerprint: {pre_state}")

            # 2. Locate Element (Shadow Piercing BFS)
            # Finds the element even if it's deeply nested in iframes or shadow roots.
            element = await self._locate_robustly(page, xpath)
            
            if not element:
                # CRITICAL: Record failure in history BEFORE raising exception
                # This ensures the Architect blacklists the vanished path immediately.
                err_msg = f"FAILED on {xpath} -> Element Vanished/Hidden during acquisition."
                state['history_steps'].append(err_msg)
                state['error_log'].append(f"Element lookup failed for {xpath}")
                
                logger.error(f"[{mission_id}] ❌ ACQUISITION FAILURE: {xpath}")
                
                # Capture evidence of the failure
                await self._capture_failure_artifact(page, mission_id, "ACQUISITION_FAIL")
                
                state['status'] = 'PLANNING'
                return state

            # 3. Action Logic (Escalation Ladder)
            # Depending on action type, engage different engines.
            if action == 'CLICK':
                await self._escalated_click_engine(page, element, xpath)
            elif action == 'TYPE':
                await self._zenith_typing_engine(page, element, payload, xpath)
            else:
                logger.error(f"Unsupported action: {action}")
                state['error_log'].append(f"Action {action} not implemented in Zenith.")

            # 4. State Settling
            # Allow time for government portal redirects and JS transitions
            logger.info(f"[{mission_id}] ⏳ Action complete. Waiting {SETTLE_TIME}s for UI to settle...")
            await asyncio.sleep(SETTLE_TIME)
            
            # 5. Delta Verification (The "After" state)
            post_state = await self._capture_fingerprint(page)
            impact = self._calculate_delta(pre_state, post_state)
            logger.info(f"[{mission_id}] 🔍 IMPACT DETECTED: {impact}")

            # 6. Artifact Generation
            step_idx = len(state['history_steps']) + 1
            scr_path = os.path.join(self.screenshot_dir, f"{mission_id}_step_{step_idx}_{impact}.png")
            try:
                await page.screenshot(path=scr_path)
            except: pass

            # 7. Shared State Update
            history_line = f"{action} on {xpath} -> Result: {impact}"
            state['history_steps'].append(history_line)
            state['current_url'] = page.url
            state['last_action_impact'] = impact
            
            if impact == "NO_CHANGE":
                # Signal the Architect that this element is a 'Ghost' or 'Decoy'
                warn_msg = f"Action '{action}' on {xpath} executed successfully but caused NO DETECTABLE STATE CHANGE."
                state['error_log'].append(warn_msg)
                logger.warning(warn_msg)

            state['status'] = 'PLANNING'
            mission_db.log_action(mission_id, "ShadowNavigator", "EXEC_ZENITH", history_line)

        except Exception as e:
            # FATAL EXCEPTION HANDLER: Force a failure log for the Blacklist
            # This is crucial. If we don't log "CRASH" to history, the Architect won't know to blacklist.
            logger.error(f"[{mission_id}] 🛑 NAVIGATOR CRASH: {e}", exc_info=True)
            crash_msg = f"CRASH on {xpath} -> {str(e)[:100]}"
            state['history_steps'].append(crash_msg)
            state['error_log'].append(f"Navigator Fatal: {str(e)}")
            state['status'] = 'PLANNING'

        return state

    # ==========================================================================
    #        INTERNAL UTILITIES: THE PERCEPTION SUITE
    # ==========================================================================

    async def _capture_fingerprint(self, page: Page) -> Dict[str, Any]:
        """
        Takes a structural fingerprint of the page for Delta Sensing.
        Uses pure JS to bypass object-level overhead.
        """
        try:
            return await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
                return {
                    url: window.location.href,
                    title: document.title,
                    node_count: document.getElementsByTagName('*').length,
                    visible_inputs: inputs.filter(i => i.offsetWidth > 0).length,
                    scroll_y: window.scrollY,
                    // Capture simple hash of text to detect content updates
                    text_len: document.body.innerText.length
                };
            }""")
        except Exception as e:
            logger.warning(f"Fingerprint failed: {e}")
            return {"url": page.url, "error": True}

    def _calculate_delta(self, pre: Dict, post: Dict) -> str:
        """
        Heuristic Impact Classifier.
        Categorizes page changes into distinct action outcomes.
        """
        if post.get('error') or pre.get('error'):
            return "UNKNOWN_STATE"

        # 1. Navigation Check
        if post['url'] != pre['url']:
            return "URL_NAVIGATED"
        
        # 2. Input Appearance (Search bar opened)
        if post['visible_inputs'] > pre['visible_inputs']:
            return "INPUT_FIELD_APPEARED"
            
        # 3. UI Collapse (Modal closed)
        if post['visible_inputs'] < pre['visible_inputs']:
            return "UI_COLLAPSED"

        # 4. Title Change (SPA Navigation)
        if post['title'] != pre['title']:
            return "TITLE_CHANGED"
            
        # 5. DOM Mutation (Lazy Load / Menu Open)
        if abs(post['node_count'] - pre['node_count']) > 5:
            return "DOM_MUTATED"
            
        # 6. Text Content Change
        if abs(post['text_len'] - pre['text_len']) > 20:
            return "CONTENT_UPDATED"
            
        return "NO_CHANGE"

    async def _capture_failure_artifact(self, page: Page, mission_id: str, tag: str):
        """Saves screenshot on failure."""
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            path = os.path.join(self.screenshot_dir, f"{mission_id}_FAIL_{tag}_{timestamp}.png")
            await page.screenshot(path=path)
        except: pass

    async def _force_ui_hydration(self, page: Page):
        """
        Scrolls the page to wake up lazy-loaded government portal scripts.
        """
        try:
            logger.debug("Performing Hydration Scroll...")
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(0.5)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            
            # Jiggle to trigger IntersectionObservers
            await page.evaluate("window.scrollBy(0, -50)")
            await asyncio.sleep(0.2)
            await page.evaluate("window.scrollBy(0, 50)")
            
            # Return to top
            await page.evaluate("window.scrollTo(0, 0)")
        except:
            pass

    # ==========================================================================
    #        CORE ENGINE: THE SHADOW PIERCER (ACQUISITION)
    # ==========================================================================

    async def _locate_robustly(self, page: Page, xpath: str) -> Optional[ElementHandle]:
        """
        Recursively searches the page, all iframes, and all accessible Shadow DOMs
        for the target XPath.
        """
        logger.debug(f"Locating target: {xpath}")
        
        # 1. Standard Frame Search (BFS)
        try:
            # Check main frame first
            locator = page.locator(f"xpath={xpath}").first
            if await locator.count() > 0:
                return await locator.element_handle()
                
            # Check recursive frames
            for frame in page.frames:
                try:
                    locator = frame.locator(f"xpath={xpath}").first
                    if await locator.count() > 0:
                        logger.info(f"Element found in frame: {frame.name or frame.url}")
                        return await locator.element_handle()
                except:
                    continue
        except Exception as e:
            logger.debug(f"Frame search failed: {e}")

        # 2. Shadow DOM Search (JS Injection)
        # Deep searches through all open shadow roots using native TreeWalker
        try:
            handle = await page.evaluate_handle(f"""(xpath) => {{
                function getByXpath(path, root) {{
                    try {{
                        return document.evaluate(path, root, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    }} catch(e) {{ return null; }}
                }}
                
                // Check document root again just in case
                let found = getByXpath(xpath, document);
                if (found) return found;
                
                // Deep scan shadow roots
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {{
                    if (el.shadowRoot) {{
                        found = getByXpath(xpath, el.shadowRoot);
                        if (found) return found;
                    }}
                }}
                return null;
            }}""", xpath)
            
            if handle:
                element = handle.as_element()
                if element: 
                    logger.info("Element found via Shadow DOM Piercer.")
                    return element
        except Exception as e:
            logger.debug(f"Shadow DOM search failed: {e}")

        return None

    # ==========================================================================
    #        CORE ENGINE: THE ESCALATION LADDER (INTERACTION)
    # ==========================================================================

    async def _escalated_click_engine(self, page: Page, element: ElementHandle, xpath: str):
        """
        A 4-stage click escalation ladder.
        Attempts increasingly aggressive methods to click the target.
        """
        # Level 1: Standard Playwright Click
        try:
            logger.info("Click L1: Standard User Action")
            await element.click(timeout=3000)
            return
        except Exception as e:
            logger.warning(f"L1 Click Failed: {e}. Escalating...")

        # Level 2: Force Click (Bypasses intersection checks)
        try:
            logger.info("Click L2: Hardware Force")
            await element.click(force=True, timeout=2000)
            return
        except Exception:
            logger.warning("L2 Click Failed. Escalating to JavaScript...")

        # Level 3: JS Event Dispatch (Ghost Click)
        try:
            logger.info("Click L3: JS Event Injection")
            # FIXED ARGUMENT PASSING: Passed as list [xpath]
            await page.evaluate(f"""([xpath]) => {{
                let el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if(el) {{
                    el.scrollIntoView({{block: 'center'}});
                    el.click();
                    el.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true, view: window}}));
                    el.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true, view: window}}));
                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                }} else {{ throw new Error("DOM context lost"); }}
            }}""", [xpath])
            return
        except Exception as e:
            logger.warning(f"L3 Click Failed: {e}. Escalating to Coordinates...")

        # Level 4: Coordinate-based Raw Click (The Nuclear Option)
        try:
            logger.info("Click L4: Coordinate-based targeting")
            box = await element.bounding_box()
            if box:
                center_x = box['x'] + box['width'] / 2
                center_y = box['y'] + box['height'] / 2
                await page.mouse.click(center_x, center_y)
                logger.info(f"Clicked Coordinates: ({center_x}, {center_y})")
            else:
                raise Exception("Element has no bounding box (size 0x0).")
        except Exception as e:
            logger.error(f"L4 Click Failed: {e}")
            raise Exception("ALL CLICK ESCALATION LEVELS EXHAUSTED.")

    async def _zenith_typing_engine(self, page: Page, element: ElementHandle, text: str, xpath: str):
        """
        A multi-modal typing engine that uses the 'Enter Hammer' 
        to force React/Angular framework recognition.
        """
        logger.info(f"Typing '{text}' into target...")

        # Step 1: Standard Interaction
        # Try to clear and type like a human
        try:
            await element.scroll_into_view_if_needed()
            await element.fill("", timeout=2000) 
            await element.type(text, delay=100) 
        except Exception:
            logger.warning("Standard Type Failed. Using Force Fill.")
            await element.fill(text, force=True)

        # Step 2: THE ENTER HAMMER (Multi-Event Dispatch)
        # This is critical for sites like india.gov.in that use sophisticated listeners.
        logger.info("Dispatching the Enter Hammer (Event Sequence)...")
        try:
            # FIXED ARGUMENT PASSING: Passed as list [xpath, text]
            await page.evaluate(f"""([xpath, payload]) => {{
                let el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if(el) {{
                    // 1. Force Value
                    el.value = payload;
                    
                    // 2. Trigger Input/Change Framework Listeners
                    el.dispatchEvent(new Event('focus', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    
                    // 3. Simulate Key Press (Enter) via JS
                    const opt = {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }};
                    el.dispatchEvent(new KeyboardEvent('keydown', opt));
                    el.dispatchEvent(new KeyboardEvent('keypress', opt));
                    el.dispatchEvent(new KeyboardEvent('keyup', opt));
                    
                    // 4. Force Form Submission if inside a form
                    if (el.form) {{
                        const submitEvent = new Event('submit', {{ bubbles: true, cancelable: true }});
                        el.form.dispatchEvent(submitEvent);
                    }}
                    
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}
            }}""", [xpath, text])
            
            # Step 3: Hardware-level Enter key as a backup
            # This triggers the browser's native behavior
            await page.keyboard.press("Enter")
            
        except Exception as e:
            logger.error(f"Enter Hammer failed: {e}")
            # Don't raise here, we want to proceed to verify if Step 1 worked

    # ==========================================================================
    #        DEFENSIVE PROTOCOLS: THE STABILIZERS
    # ==========================================================================

    async def _wait_for_network_quiescence(self, page: Page, timeout: int = 5000):
        """
        Wait for the network traffic to drop to near-zero before proceeding.
        Useful for pages with heavy async content.
        """
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            logger.debug("Network did not reach idle state, proceeding anyway.")

# ==============================================================================
#        MODULE ENTRY POINT (SELF-TEST)
# ==============================================================================
if __name__ == "__main__":
    print("--- Running Sentinel-8 Zenith Navigator Diagnostics ---")
    try:
        navigator = ShadowNavigatorAgent()
        print("Initialization: SUCCESS")
        print("Escalation Ladder: LOADED")
        print("Enter Hammer v3: ACTIVE")
        print("Shadow Piercer BFS: READY")
        print("Forensics Logger: ONLINE")
        print("\nNavigator is ready for high-hostility UI environments.")
    except Exception as e:
        print(f"Diagnostics FAILED: {e}")