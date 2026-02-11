"""
Drishti-AX: Main Agent Runner (The Absolute Orchestrator)
Module: main_agent_runner.py
Version: Sentinel-10.3 "Absolute"
Author: Sentinel Core System
Timestamp: 2026-02-12 10:00:00 UTC

Description:
    The fault-tolerant central nervous system of the autonomous squad.
    This module orchestrates the lifecycle of 5 agents, manages the browser
    context, enforces safety protocols, and records forensic evidence.

    CRITICAL FIXES v10.3:
    - FIXED: Windows `logging` ValueError (Invalid format string).
    - FIXED: Configuration attribute mismatch (`nav_timeout`).
    - FIXED: Database Proxy method delegation.
    - FIXED: Browser hydration method signature.

    ARCHITECTURAL LAYERS:
    -------------------------------------------------------------------------
    LAYER 0: FOUNDATION
        - Configuration Management (Dataclasses).
        - Advanced Logging (Windows-Safe ANSI).
        - Path Management & Workspace Sanitization.

    LAYER 1: RESILIENCE
        - NeuralCircuitBreaker: Exponential backoff decorators.
        - SystemMonitor: Real-time RAM/CPU telemetry.
        - SignalHandler: Graceful shutdown.

    LAYER 2: INFRASTRUCTURE
        - DatabaseProxy: Fault-tolerant wrapper for storage.
        - BrowserEngine: Playwright wrapper with CDP stealth.
        - ForensicsLab: Artifact collection.

    LAYER 3: THE SQUAD (DEPENDENCY INJECTION)
        - SquadController: State container and agent loader.
        - MockSwarm: Fallback implementations.

    LAYER 4: THE REACTOR (CORE LOGIC)
        - Finite State Machine (FSM).
        - SafetyMonitor & ContextNuke.
    -------------------------------------------------------------------------
"""

import asyncio
import logging
import os
import sys
import json
import time
import shutil
import signal
import platform
import random
import re
import traceback
import uuid
import functools
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple, Callable, Type

# Optional PSUtil import
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# ==============================================================================
#        SECTION 1: CONFIGURATION & CONSTANTS
# ==============================================================================

# Unique Execution Hash
EXECUTION_ID = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

@dataclass
class PathConfig:
    """Directory structure definition."""
    base: str = os.path.dirname(os.path.abspath(__file__))
    reports: str = os.path.join(base, "reports")
    logs: str = os.path.join(reports, "logs")
    evidence: str = os.path.join(reports, "evidence")
    data: str = os.path.join(reports, "data")
    temp: str = os.path.join(reports, "temp")

@dataclass
class BrowserConfig:
    """Browser runtime settings."""
    headless: bool = False
    slow_mo: int = 50
    width: int = 1920
    height: int = 1080
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"
    stealth: bool = True
    har_recording: bool = False

@dataclass
class MissionConfig:
    """Operational parameters."""
    target_url: str = "https://www.india.gov.in"
    goal: str = "Find the search input box and the search button."
    max_steps: int = 60
    step_delay: float = 2.0
    action_timeout: int = 30000
    nav_timeout: int = 60000
    max_retries: int = 5
    safety_brake_threshold: int = 3

@dataclass
class GlobalConfig:
    """Master configuration object."""
    paths: PathConfig = field(default_factory=PathConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    mission: MissionConfig = field(default_factory=MissionConfig)
    debug_mode: bool = True
    use_mocks: bool = False

# Initialize Global Configuration
CFG = GlobalConfig()

# Bootstrap Dirs
for p in [CFG.paths.reports, CFG.paths.logs, CFG.paths.evidence, CFG.paths.data, CFG.paths.temp]:
    os.makedirs(p, exist_ok=True)

# ==============================================================================
#        SECTION 2: ADVANCED LOGGING (WINDOWS SAFE)
# ==============================================================================

class AbsoluteFormatter(logging.Formatter):
    """
    High-fidelity ANSI logging formatter.
    WINDOWS SAFE: Uses basic time formatting.
    """
    
    GREY = "\x1b[38;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMAT_STR = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"

    FORMATS = {
        logging.DEBUG: GREY + FORMAT_STR + RESET,
        logging.INFO: GREEN + FORMAT_STR + RESET,
        logging.WARNING: YELLOW + FORMAT_STR + RESET,
        logging.ERROR: RED + FORMAT_STR + RESET,
        logging.CRITICAL: BOLD_RED + FORMAT_STR + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        # CRITICAL FIX: Removed %f for Windows compatibility
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

def get_logger(name: str) -> logging.Logger:
    """Factory for creating configured loggers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    if not logger.handlers:
        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(AbsoluteFormatter())
        logger.addHandler(ch)
        
        # File Handler
        fh = logging.FileHandler(
            os.path.join(CFG.paths.logs, f"session_{EXECUTION_ID}.log"),
            encoding='utf-8'
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S"))
        logger.addHandler(fh)
        
    return logger

SYS_LOG = get_logger("SYSTEM")

# ==============================================================================
#        SECTION 3: RESILIENCE LAYER
# ==============================================================================

class NeuralCircuitBreaker:
    """Decorators for fault tolerance."""
    
    @staticmethod
    def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                attempts = 0
                current_delay = delay
                while attempts < max_attempts:
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        attempts += 1
                        if attempts >= max_attempts:
                            SYS_LOG.error(f"Function {func.__name__} failed: {e}")
                            raise e
                        SYS_LOG.warning(f"Retry {attempts}/{max_attempts} for {func.__name__}: {e}")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            return wrapper
        return decorator

class SystemMonitor:
    """Monitors host resources."""
    @staticmethod
    def check_health():
        if not PSUTIL_AVAILABLE: return
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                SYS_LOG.critical(f"MEMORY CRITICAL: {mem.percent}% used.")
        except: pass

# ==============================================================================
#        SECTION 4: INFRASTRUCTURE (DB & BROWSER)
# ==============================================================================

# --- DATABASE PROXY ---

class DatabaseProxy:
    """
    Fault-tolerant wrapper for the Mission Database.
    Prevents AttributeError if methods are missing on legacy DB implementations.
    """
    def __init__(self, real_db=None):
        self.real_db = real_db
        if not real_db:
            SYS_LOG.warning("⚠️ Running with MOCK DATABASE. Persistence disabled.")

    def start_mission(self, state: Dict):
        if self.real_db and hasattr(self.real_db, 'start_mission'):
            self.real_db.start_mission(state)
        else:
            SYS_LOG.info(f"[DB PROXY] Mission {state['mission_id']} Started.")

    def log_action(self, mid: str, agt: str, act: str, det: Any):
        if self.real_db and hasattr(self.real_db, 'log_action'):
            self.real_db.log_action(mid, agt, act, det)

    def update_state_snapshot(self, state: Dict):
        """Intercepts calls and handles missing methods safely."""
        if self.real_db:
            if hasattr(self.real_db, 'update_state_snapshot'):
                self.real_db.update_state_snapshot(state)
            elif hasattr(self.real_db, 'update_state'):
                self.real_db.update_state(state)
        # If neither exists, we just silently continue without crashing

class MockDatabase:
    """Fallback if no DB is present."""
    pass

# --- BROWSER ENGINE ---

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    SYS_LOG.critical("Playwright import failed.")
    sys.exit(1)

class BrowserEngine:
    """
    Manages the Playwright lifecycle with advanced configuration.
    """
    def __init__(self, config: BrowserConfig):
        self.cfg = config
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logger = get_logger("BROWSER")

    async def initialize(self):
        """Boots the browser."""
        self.logger.info("Igniting Chromium Engine...")
        self.playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--start-maximized',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-features=IsolateOrigins,site-per-process'
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=self.cfg.headless,
            slow_mo=self.cfg.slow_mo,
            args=args
        )
        self.logger.info("Chromium Engine Online.")

    async def create_context(self) -> Page:
        """Creates a specialized stealth context."""
        self.context = await self.browser.new_context(
            viewport={'width': self.cfg.width, 'height': self.cfg.height},
            user_agent=self.cfg.user_agent,
            locale=self.cfg.locale,
            timezone_id=self.cfg.timezone
        )
        
        # Inject Stealth Scripts
        js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.navigator.chrome = { runtime: {} };
        """
        await self.context.add_init_script(js)
        
        self.page = await self.context.new_page()
        
        # Hook Console Logs
        self.page.on("console", self._handle_console)
        self.page.on("pageerror", self._handle_error)
        
        return self.page

    def _handle_console(self, msg):
        if msg.type in ["error", "warning"]:
            self.logger.debug(f"[CONSOLE] {msg.text}")

    def _handle_error(self, err):
        self.logger.warning(f"[PAGE CRASH] {err}")

    async def hydrate_page(self):
        """
        Executes the 'Hydration Jiggle' to wake up lazy-loaded elements.
        FIXED: Explicit definition prevents AttributeError.
        """
        self.logger.debug("Executing Hydration Protocols...")
        try:
            # Scroll Down
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(0.5)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            
            # Jiggle
            await self.page.evaluate("window.scrollBy(0, -100)")
            await asyncio.sleep(0.2)
            await self.page.evaluate("window.scrollBy(0, 100)")
            
            # Return to Top
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except Exception as e:
            self.logger.warning(f"Hydration warning: {e}")

    async def shutdown(self):
        """Graceful teardown."""
        self.logger.info("Shutting down Browser...")
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

# ==============================================================================
#        SECTION 6: FORENSICS LAB
# ==============================================================================

class ForensicsLab:
    """
    Artifact collection service.
    """
    def __init__(self, mission_id: str):
        self.mid = mission_id
        self.logger = get_logger("FORENSICS")

    async def capture_snapshot(self, page: Page, phase: str, step: int):
        """Captures Screenshot and DOM."""
        if not page: return
        tag = f"{self.mid}_step_{step:02d}_{phase}"
        
        try:
            path = os.path.join(CFG.paths.evidence, f"{tag}.png")
            await page.screenshot(path=path)
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")

        try:
            path = os.path.join(CFG.paths.evidence, f"{tag}.html")
            content = await page.content()
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"DOM Dump failed: {e}")

    def generate_report(self, state: Dict):
        """Serializes final state to JSON."""
        path = os.path.join(CFG.paths.data, f"report_{self.mid}.json")
        try:
            clean = self._clean_state(state)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(clean, f, indent=4, default=str)
            self.logger.info(f"Report Generated: {path}")
        except Exception as e:
            self.logger.error(f"Report Failed: {e}")

    def _clean_state(self, state: Dict) -> Dict:
        return {
            "meta": {
                "id": state.get('mission_id'),
                "target": state.get('target_url'),
                "status": state.get('status'),
                "timestamp": datetime.now().isoformat()
            },
            "stats": {
                "steps": len(state.get('history_steps', [])),
                "errors": len(state.get('error_log', []))
            },
            "history": state.get('history_steps', []),
            "errors": state.get('error_log', []),
            "blacklist": state.get('hard_blacklist', {})
        }

# ==============================================================================
#        SECTION 7: SQUAD CONTROLLER
# ==============================================================================

class SquadController:
    """
    Manages the 5-Agent Squad lifecycle.
    """
    def __init__(self, db: DatabaseProxy, config: MissionConfig):
        self.db = db
        self.cfg = config
        self.mid = f"MISSION_{datetime.now().strftime('%m%d_%H%M')}_{uuid.uuid4().hex[:4]}"
        self.logger = get_logger("SQUAD")
        
        self.state = {
            "mission_id": self.mid,
            "target_url": config.target_url,
            "goal": config.goal,
            "status": "STARTED",
            "history_steps": [],
            "error_log": [],
            "dom_snapshot": [],
            "current_url": config.target_url,
            "is_complete": False,
            "last_action_impact": None,
            "hard_blacklist": {"xpaths": [], "ids": [], "containers": [], "quarantine": []}
        }
        
        self.architect = None
        self.sensor = None
        self.navigator = None
        self.surgeon = None
        self.warden = None
        
        self.db.start_mission(self.state)

    def load_agents(self):
        """Loads agent modules, falling back to mocks if requested."""
        self.logger.info("Mobilizing Agents...")
        
        if CFG.use_mocks:
            self._load_mocks()
            return

        try:
            from agents.mission_architect import MissionArchitectAgent
            from agents.semantic_sensor import SemanticSensorAgent
            from agents.shadow_navigator import ShadowNavigatorAgent
            from agents.patch_surgeon import PatchSurgeonAgent
            from agents.quality_warden import QualityWardenAgent
            
            self.architect = MissionArchitectAgent()
            self.sensor = SemanticSensorAgent()
            self.navigator = ShadowNavigatorAgent()
            self.surgeon = PatchSurgeonAgent()
            self.warden = QualityWardenAgent()
            
            self.logger.info("Real Agents Loaded Successfully.")
        except ImportError as e:
            self.logger.error(f"Agent Import Failed: {e}. Falling back to Mocks.")
            self._load_mocks()

    def _load_mocks(self):
        self.logger.warning("Initializing MOCK SWARM.")
        self.architect = MockArchitect()
        self.sensor = MockSensor()
        self.navigator = MockNavigator()
        self.surgeon = MockSurgeon()
        self.warden = MockWarden()

# --- MOCK AGENTS ---
class MockArchitect:
    def plan(self, s): 
        s['status'] = 'NAVIGATING'
        s['semantic_map'] = {'target_xpath': '//mock', 'action_type': 'CLICK'}
        return s
class MockNavigator:
    async def execute(self, s, p):
        s['history_steps'].append("Mock Action Executed")
        s['status'] = 'PLANNING'
        return s
class MockSensor:
    def analyze(self, s): s['status'] = 'PLANNING'; return s
class MockSurgeon:
    def heal(self, s): return s
class MockWarden:
    async def verify_fixes(self, s): return s

# ==============================================================================
#        SECTION 8: MISSION REACTOR (CORE LOOP)
# ==============================================================================

# V7.1 Deep Scan JS
DEEP_SCAN_JS = """
() => {
    const results = [];
    const scan = (root) => {
        const els = root.querySelectorAll('button, a, input, select, textarea, [role="button"], form');
        els.forEach(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const isVisible = (rect.width > 0 || rect.height > 0) && (style.display !== 'none');
            if (isVisible) {
                results.push({
                    tag: el.tagName,
                    text: (el.innerText || el.value || "").trim().substring(0, 50),
                    xpath: `//*[@id='${el.id}']` || `//${el.tagName}`,
                    visible: true,
                    attributes: {id: el.id}
                });
            }
            if (el.shadowRoot) scan(el.shadowRoot);
        });
    };
    if (document.body) scan(document.body);
    return results.slice(0, 300);
}
"""

class MissionReactor:
    """The Finite State Machine."""
    def __init__(self, squad: SquadController, browser: BrowserEngine, forensics: ForensicsLab):
        self.squad = squad
        self.browser = browser
        self.forensics = forensics
        self.logger = get_logger("REACTOR")
        self.step = 0

    @NeuralCircuitBreaker.retry(max_attempts=3)
    async def run(self):
        """Main Execution Loop."""
        self.logger.info(f"Reactor Online. Mission: {self.squad.mid}")
        
        try:
            while self._should_continue():
                self.step += 1
                phase = self.squad.state['status']
                self.logger.info(f"--- [STEP {self.step}] PHASE: {phase} ---")
                
                SystemMonitor.check_health()
                
                # Pre-Step Snapshot
                # await self.forensics.capture_snapshot(self.browser.page, "PRE", self.step)

                await self._dispatch_phase(phase)
                
                # Post-Step Snapshot
                # await self.forensics.capture_snapshot(self.browser.page, "POST", self.step)
                
                # Housekeeping via Proxy
                self.squad.db.update_state_snapshot(self.squad.state)
                await asyncio.sleep(CFG.mission.step_delay)

        except Exception as e:
            self.logger.critical(f"Reactor Meltdown: {e}", exc_info=True)
            self.squad.state['status'] = "FAILED"
            await self.forensics.capture_snapshot(self.browser.page, "FATAL", self.step)
        
        finally:
            self.forensics.generate_report(self.squad.state)

    def _should_continue(self) -> bool:
        s = self.squad.state
        if s['is_complete'] or s['status'] in ["FAILED", "ABORTED"]: return False
        if self.step >= CFG.mission.max_steps: return False
        return True

    async def _dispatch_phase(self, phase: str):
        if phase in ["STARTED", "PLANNING"]:
            await self._phase_planning()
        elif phase == "ANALYZING":
            await self._phase_perception()
        elif phase == "NAVIGATING":
            await self._phase_action()
        elif phase in ["FIXING", "VERIFYING"]:
            await self._phase_remediation(phase)
        else:
            self.logger.error(f"Unknown Phase: {phase}")
            self.squad.state['status'] = "PLANNING"

    async def _phase_planning(self):
        state = self.squad.state
        
        if state['status'] == "STARTED":
            self.logger.info(f"Navigating to Target: {state['target_url']}")
            try:
                # FIXED: Used correct Config attribute 'nav_timeout'
                await self.browser.page.goto(state['target_url'], timeout=CFG.mission.nav_timeout)
                await self.browser.hydrate_page()
                state['current_url'] = self.browser.page.url
                state['status'] = "ANALYZING"
            except Exception as e:
                self.logger.error(f"Initial Navigation Failed: {e}")
                state['status'] = "FAILED"
            return

        # Safety Brake
        hist = state.get('history_steps', [])
        if len(hist) >= CFG.mission.safety_brake_threshold:
            recent = hist[-CFG.mission.safety_brake_threshold:]
            if all(x == recent[0] for x in recent):
                self.logger.warning(">>> SAFETY BRAKE: Loop Detected. Rescanning. <<<")
                state['status'] = "ANALYZING"
                return

        # Context Nuke
        if state.get('last_action_impact') == "URL_NAVIGATED":
            self.logger.info(">>> CONTEXT NUKE: URL Changed. Rescanning. <<<")
            state['status'] = "ANALYZING"
            state['dom_snapshot'] = []
            state['last_action_impact'] = None
            return

        # Execute Architect
        self.squad.state = self.squad.architect.plan(state)

    async def _phase_perception(self):
        self.logger.info("Scanning DOM...")
        try:
            dom = await self.browser.page.evaluate(DEEP_SCAN_JS)
            if dom and len(dom) > 0:
                self.squad.state['dom_snapshot'] = dom
                self.squad.state['current_url'] = self.browser.page.url
                self.squad.state = self.squad.sensor.analyze(self.squad.state)
            else:
                self.logger.warning("DOM Empty. Retrying...")
                await asyncio.sleep(1)
                self.squad.state['status'] = "PLANNING"
        except Exception as e:
            self.logger.error(f"Scan Failed: {e}")
            self.squad.state['status'] = "PLANNING"

    async def _phase_action(self):
        self.squad.state = await self.squad.navigator.execute(self.squad.state, self.browser.page)

    async def _phase_remediation(self, phase: str):
        if phase == "FIXING":
            self.squad.state = self.squad.surgeon.heal(self.squad.state)
        elif phase == "VERIFYING":
            self.squad.state = await self.squad.warden.verify_fixes(self.squad.state)

# ==============================================================================
#        SECTION 9: MAIN EXECUTION FLOW
# ==============================================================================

async def entry_point():
    """Bootstraps the Singularity Runtime."""
    
    # 1. Parse Args
    parser = argparse.ArgumentParser(description="Sentinel-10.3 Absolute Runner")
    parser.add_argument("--url", default=CFG.mission.target_url)
    parser.add_argument("--goal", default=CFG.mission.goal)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    # Apply Config
    CFG.mission.target_url = args.url
    CFG.mission.goal = args.goal
    CFG.use_mocks = args.mock
    CFG.browser.headless = args.headless

    SYS_LOG.info(f"Booting Sentinel-10.3 (ID: {EXECUTION_ID})")
    
    # 2. Dependency Resolution
    try:
        from cognition.state_manager import mission_db as real_db
        db_adapter = DatabaseProxy(real_db)
    except ImportError:
        db_adapter = DatabaseProxy(MockDatabase())

    # 3. Initialization
    browser = BrowserEngine(CFG.browser)
    squad = SquadController(db_adapter, CFG.mission)
    forensics = ForensicsLab(squad.mid)
    
    # 4. Load
    squad.load_agents()
    
    # 5. Launch
    await browser.initialize()
    await browser.create_context()
    
    # 6. Ignite Reactor
    reactor = MissionReactor(squad, browser, forensics)
    
    start_time = time.time()
    try:
        await reactor.run()
    finally:
        await browser.shutdown()
        dur = time.time() - start_time
        SYS_LOG.info(f"System Shutdown. Runtime: {dur:.2f}s")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(entry_point())
    except KeyboardInterrupt:
        SYS_LOG.warning("Hard Stop received (SIGINT).")
        sys.exit(0)
    except Exception as fatal:
        SYS_LOG.critical(f"FATAL SYSTEM ERROR: {fatal}", exc_info=True)
        sys.exit(1)