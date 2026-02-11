import asyncio
import logging
import os
import sys
import json
import time
from datetime import datetime

# Third-party imports
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[CRITICAL] Playwright not installed.")
    sys.exit(1)

# ==========================================
#        CRITICAL SETUP & DIRS
# ==========================================
# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Define Directory Structure
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
EVIDENCE_DIR = os.path.join(REPORT_DIR, "evidence")
DATA_DIR = os.path.join(REPORT_DIR, "data")
LOGS_DIR = os.path.join(REPORT_DIR, "logs")

# Force Create Directories
for d in [REPORT_DIR, EVIDENCE_DIR, DATA_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

# ==========================================
#        LOGGING CONFIGURATION
# ==========================================
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError: pass

logger = logging.getLogger("SENTINEL_COMMANDER")
logger.setLevel(logging.INFO)

# File Handler
file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "mission_log.txt"), mode='a', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
logger.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
logger.addHandler(console_handler)

# Import Agents (Safe Import)
try:
    from agents.mission_architect import MissionArchitectAgent
    from agents.semantic_sensor import SemanticSensorAgent
    from agents.shadow_navigator import ShadowNavigatorAgent
    from agents.patch_surgeon import PatchSurgeonAgent
    from agents.quality_warden import QualityWardenAgent
    from cognition.state_manager import mission_db
except ImportError as e:
    logger.critical(f"Failed to import Agents: {e}")
    sys.exit(1)

# ==========================================
#        STEALTH & EXTRACTION SCRIPTS
# ==========================================
# Stealth Script to bypass Bot Detection (Akamai/Cloudflare)
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
window.navigator.chrome = {
    runtime: {},
};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);
"""

# CORRECTED DEEP_SCAN_JS (Validation: Verified Safe Syntax)
# This payload recursively scans Shadow DOMs and frames
DEEP_SCAN_JS = """
() => {
    const results = [];
    
    // Helper: Generate robust XPath
    const getXpath = (el) => {
        if (el.id) return `//*[@id="${el.id}"]`;
        const parts = [];
        while (el && el.nodeType === 1) {
            let nb = 0;
            let siblings = el.parentNode ? el.parentNode.childNodes : [];
            for (let i = 0; i < siblings.length; i++) {
                let s = siblings[i];
                if (s === el) {
                    parts.unshift(el.tagName.toLowerCase() + '[' + (nb + 1) + ']');
                    break;
                }
                if (s.nodeType === 1 && s.tagName === el.tagName) nb++;
            }
            el = el.parentNode;
        }
        return parts.length ? '/' + parts.join('/') : null;
    };

    // Recursive Scanner
    const scan = (root) => {
        const els = root.querySelectorAll('button, a, input, select, textarea, [role="button"], [onclick], form, div[role="search"]');
        
        els.forEach(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            
            // Logic: Include if physically visible OR if it's an input (even hidden ones need tracking)
            const isVisible = (rect.width > 0 || rect.height > 0 || el.tagName === 'INPUT') && 
                              (style.display !== 'none' && style.visibility !== 'hidden');
            
            if (isVisible) {
                let text = (el.innerText || el.placeholder || el.value || el.getAttribute('aria-label') || "").trim();
                // Clean text to remove massive whitespace
                text = text.replace(/[\\n\\r]+/g, ' ').substring(0, 100); 
                
                results.push({
                    tag: el.tagName,
                    text: text,
                    xpath: getXpath(el),
                    visible: true, // We assume visible if it passed the check
                    attributes: { 
                        id: el.id, 
                        role: el.getAttribute('role'),
                        type: el.getAttribute('type'),
                        href: el.getAttribute('href'),
                        class: el.className
                    }
                });
            }
            
            // Recurse into Shadow Root
            if (el.shadowRoot) {
                scan(el.shadowRoot);
            }
        });
    };

    if (document.body) {
        scan(document.body);
    }
    
    // Limit to prevent token overflow, but prioritize 'search' related items
    return results.slice(0, 300); 
}
"""

def save_final_report(state):
    """
    Saves the full mission state to JSON for forensic analysis.
    """
    mission_id = state['mission_id']
    filename = f"report_{mission_id}.json"
    filepath = os.path.join(DATA_DIR, filename)
    
    report_data = {
        "metadata": {
            "mission_id": mission_id,
            "target_url": state['target_url'],
            "goal": state['goal'],
            "timestamp": datetime.now().isoformat(),
            "final_status": state['status']
        },
        "execution_stats": {
            "total_steps": len(state.get('history_steps', [])),
            "errors_encountered": len(state.get('error_log', []))
        },
        "logs": {
            "history": state.get('history_steps', []),
            "errors": state.get('error_log', [])
        },
        "artifacts": {
            "last_screenshot": state.get('screenshot_path', 'N/A'),
            "dom_snapshot_size": len(state.get('dom_snapshot', []))
        }
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=4)
        logger.info(f"[REPORT] 📄 Data saved to: {filepath}")
    except Exception as e:
        logger.error(f"Failed to save JSON report: {e}")

async def run_autonomous_audit(target_url: str, goal: str):
    """
    Main Orchestration Loop for the Sentinel-6 Agent Squad.
    """
    # 1. Initialize Agents
    logger.info("Initializing Agent Squad...")
    architect = MissionArchitectAgent()
    sensor = SemanticSensorAgent()
    navigator = ShadowNavigatorAgent()
    surgeon = PatchSurgeonAgent()
    warden = QualityWardenAgent()

    # 2. Initialize State
    mission_id = f"MISSION_{datetime.now().strftime('%m%d_%H%M')}"
    state = {
        "mission_id": mission_id,
        "target_url": target_url,
        "goal": goal,
        "status": "STARTED",
        "history_steps": [],
        "error_log": [],
        "dom_snapshot": [],
        "current_url": target_url,
        "is_complete": False,
        "last_action_impact": None
    }
    
    mission_db.start_mission(state)
    logger.info(f"[INIT] Mission {mission_id} Launched: {goal}")

    async with async_playwright() as p:
        # 3. Launch Browser
        logger.info("Launching Browser (Visible Mode)...")
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=50,
            args=['--disable-blink-features=AutomationControlled', '--start-maximized', '--no-sandbox']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        page = await context.new_page()

        step = 0
        max_steps = 25

        try:
            while not state['is_complete'] and state['status'] != "FAILED" and step < max_steps:
                current_status = state['status']
                logger.info(f"--- [STEP {step+1}] PHASE: {current_status} ---")

                # =================================================
                # PHASE 1: PLANNING
                # =================================================
                if current_status in ["STARTED", "PLANNING"]:
                    if current_status == "STARTED":
                        logger.info(f"Navigating to {target_url}...")
                        try:
                            await page.goto(target_url, timeout=90000, wait_until='domcontentloaded')
                            logger.info("Hydrating DOM (Scrolling)...")
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await asyncio.sleep(2)
                            await page.evaluate("window.scrollTo(0, 0)")
                            
                            state['current_url'] = page.url
                            state['status'] = "ANALYZING"
                        except Exception as e:
                            logger.error(f"Initial Navigation Failed: {e}")
                            state['status'] = "FAILED"
                    else:
                        # SENTINEL-6 LOGIC: HARD RESET ON URL CHANGE
                        # If the Navigator reported a URL change, we MUST skip planning and re-scan immediately.
                        if state.get('last_action_impact') == "URL_NAVIGATED":
                             logger.info(">>> CONTEXT SWITCH DETECTED: Skipping Plan, Forcing Analysis. <<<")
                             state['status'] = "ANALYZING"
                             state['dom_snapshot'] = [] # Wipe old memory
                             state['last_action_impact'] = None # Reset flag
                        else:
                            state = architect.plan(state)

                # =================================================
                # PHASE 2: PERCEPTION
                # =================================================
                elif current_status == "ANALYZING":
                    logger.info("Initiating Deep Perception Scan...")
                    scan_attempts = 0
                    max_scan_attempts = 3
                    combined_dom = []

                    while scan_attempts < max_scan_attempts:
                        combined_dom = []
                        try:
                            # Execute Main Scan
                            main_elems = await page.evaluate(DEEP_SCAN_JS)
                            combined_dom.extend(main_elems)
                        except Exception as e:
                            logger.warning(f"Main Frame Scan Error: {e}")

                        # Execute Frame Scan
                        frames = page.frames
                        if len(frames) > 1:
                            for frame in frames[1:]:
                                try:
                                    frame_elems = await frame.evaluate(DEEP_SCAN_JS)
                                    combined_dom.extend(frame_elems)
                                except: continue

                        if len(combined_dom) > 0:
                            logger.info(f"Sensor: Successfully acquired {len(combined_dom)} elements.")
                            break
                        
                        scan_attempts += 1
                        logger.warning(f"Scan attempt {scan_attempts} returned 0 elements. Retrying in 2s...")
                        await asyncio.sleep(2)
                    
                    if not combined_dom:
                        logger.error("FATAL: DOM Scan Failed.")
                        state['status'] = "FAILED"
                    else:
                        state['dom_snapshot'] = combined_dom
                        # Update current URL in state just in case it drifted
                        state['current_url'] = page.url
                        state = sensor.analyze(state)

                # =================================================
                # PHASE 3: ACTION
                # =================================================
                elif current_status == "NAVIGATING":
                    state = await navigator.execute(state, page)

                # =================================================
                # PHASE 4 & 5: REMEDIATION & VERIFICATION
                # =================================================
                elif current_status == "FIXING":
                    state = surgeon.heal(state)

                elif current_status == "VERIFYING":
                    state = await warden.verify_fixes(state)

                step += 1
                mission_db.update_state_snapshot(state)
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.warning("Mission Aborted by User.")
            state['status'] = "ABORTED"
            
        except Exception as e:
            logger.critical(f"Critical System Failure: {e}", exc_info=True)
            state['error_log'].append(f"Critical Failure: {str(e)}")
            state['status'] = "FAILED"
            # Forensic Dump
            try:
                await page.screenshot(path=os.path.join(EVIDENCE_DIR, f"FATAL_CRASH_{mission_id}.png"))
                with open(os.path.join(EVIDENCE_DIR, f"FATAL_SOURCE_{mission_id}.html"), 'w', encoding='utf-8') as f:
                    f.write(await page.content())
            except: pass
        
        finally:
            end_msg = f"[SUCCESS] Mission Goal Achieved." if state['status'] == "COMPLETED" else f"[STOP] Mission ended: {state['status']}"
            logger.info(end_msg)
            save_final_report(state)
            await browser.close()
            logger.info("Browser Closed. Mission Terminated.")

if __name__ == "__main__":
    # CONFIGURATION
    URL = "https://www.india.gov.in"
    GOAL = "Find the search input box and the search button."
    
    # Windows Event Loop Fix
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(run_autonomous_audit(URL, GOAL))
    except KeyboardInterrupt:
        pass