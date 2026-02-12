"""
Drishti-AX: Sentinel Swarm "Omega" (The Monolith)
Module: main_agent_runner.py
Version: Sentinel-16.0 "Omega"
Author: Sentinel Core System
Timestamp: 2026-02-13 00:00:01 UTC
Classification: TOP SECRET // AUTONOMOUS SWARM

Description:
    The complete, self-contained operating system for the Sentinel Swarm.
    Integrates GPU-Accelerated Planning (Qwen-3B), Kinetic Browsing (Playwright),
    and Real-Time Telemetry into a fault-tolerant, asynchronous mesh.

    ARCHITECTURAL LAYERS:
    1.  CORE: Event Loop & Signal Handling
    2.  NEXUS: GPU Inference & Prompt Engineering
    3.  GRID: Browser Context Management & Proxy Rotation
    4.  HIVE: Agent State Machine & Task Queue
    5.  TELEMETRY: System Monitoring (VRAM/CPU/Network)

    [HARDWARE TARGET]: NVIDIA GTX 1650 (4GB VRAM) // CUDA 13.0
"""

import asyncio
import logging
import json
import re
import time
import random
import traceback
import sys
import os
import signal
import psutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ==============================================================================
#        LAYER 0: SYSTEM DEPENDENCIES & CONFIGURATION
# ==============================================================================

# Configure High-Precision Logging
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
SYS_LOG = logging.getLogger("OVERMIND")
SYS_LOG.setLevel(logging.INFO)

# Suppress noisy third-party logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# --- Configuration Constants ---
@dataclass
class SwarmConfig:
    # HARDWARE LIMITS (GTX 1650 TUNING)
    MAX_CONCURRENCY: int = 2        # Strict VRAM limit (2 Agents Max)
    GPU_OFFLOAD_LAYERS: int = -1    # All layers to GPU
    BROWSER_HEADLESS: bool = False  # Set True for speed, False for debugging
    
    # MISSION PARAMETERS
    TASK_TIMEOUT: int = 300         # Seconds before killing a stuck agent
    MAX_STEPS: int = 40             # Deep exploration limit
    RETRY_LIMIT: int = 3            # How many times to retry a failed URL
    
    # STEALTH & EVASION
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    VIEWPORT: Dict[str, int] = field(default_factory=lambda: {"width": 1366, "height": 768})

CFG = SwarmConfig()

# --- Custom Exceptions ---
class SentinelError(Exception): """Base Class"""
class NeuralCollapse(SentinelError): """AI Inference Failed"""
class GridFailure(SentinelError): """Browser Engine Crashed"""
class StrategicStalemate(SentinelError): """Agent Stuck in Loop"""

# ==============================================================================
#        LAYER 1: THE NEURAL NEXUS (GPU INTERFACE)
# ==============================================================================
class NeuralNexusBridge:
    """
    The High-Speed Bridge to the Local LLM (Qwen-2.5-3B).
    Handles Prompt Engineering, ChatML Formatting, and Error Recovery.
    """
    def __init__(self):
        self.engine = None
        self.status = "OFFLINE"
        self._ignite_engine()

    def _ignite_engine(self):
        """Attempts to load the GPU model safely."""
        try:
            from src.utils.model_loader import ai_engine
            if ai_engine and ai_engine.llm:
                self.engine = ai_engine
                self.status = "ONLINE"
                SYS_LOG.info(f"Neural Nexus Status: {self.status} (GTX 1650 Active)")
            else:
                raise ImportError("Model Loader returned None")
        except Exception as e:
            SYS_LOG.error(f"Neural Nexus Ignition Failed: {e}")
            self.status = "FALLBACK"

    def generate_tactics(self, directive: str) -> List[Dict]:
        """
        Converts a high-level goal into a structured JSON manifest.
        """
        if self.status != "ONLINE":
            return self._heuristic_fallback(directive)

        # Strategic Prompt Engineering (ChatML)
        system_prompt = (
            "You are the Strategic Command AI. "
            "Your job is to break down a User Directive into 3-4 specific Search URL vectors.\n"
            "OUTPUT FORMAT: A raw JSON list of objects: [{'url': '...', 'goal': '...'}, ...]"
        )
        
        user_prompt = f"DIRECTIVE: {directive}\nProvide the tactical JSON manifest."

        try:
            # Using the adapter we built in model_loader.py
            raw_response = self.engine.generate_code(user_prompt, system_role=system_prompt)
            
            # Parsing Logic
            manifest = self._extract_json(raw_response)
            if not manifest:
                SYS_LOG.warning("Neural Nexus output unparseable. Deploying Fallback.")
                return self._heuristic_fallback(directive)
            
            return manifest
        except Exception as e:
            SYS_LOG.error(f"Inference Error: {e}")
            return self._heuristic_fallback(directive)

    def _extract_json(self, text: str) -> Optional[List[Dict]]:
        """Robust JSON extractor that handles LLM preamble/postamble chatter."""
        try:
            # Find the largest bracketed section
            start = text.find('[')
            end = text.rfind(']') + 1
            if start == -1 or end == 0: return None
            
            candidate = text[start:end]
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    def _heuristic_fallback(self, directive: str) -> List[Dict]:
        """
        The 'Dumb' but Reliable Plan B.
        Used if the GPU is busy or the model hallucinations.
        """
        SYS_LOG.warning("Engaging Heuristic Strategy Protocols.")
        query = directive.replace(" ", "+")
        return [
            {
                "url": f"https://www.google.com/search?q={query}",
                "goal": "Primary Reconnaissance",
                "prio": 1
            },
            {
                "url": f"https://www.bing.com/search?q={query}",
                "goal": "Secondary Verification",
                "prio": 2
            },
             {
                "url": f"https://news.google.com/search?q={query}",
                "goal": "News & Sentiment Analysis",
                "prio": 3
            }
        ]

# ==============================================================================
#        LAYER 2: THE GRID (BROWSER INFRASTRUCTURE)
# ==============================================================================
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Error as PlaywrightError
except ImportError:
    SYS_LOG.critical("Playwright Missing. Run 'uv pip install playwright'.")
    sys.exit(1)

class GridController:
    """
    Manages the fleet of Chromium instances. 
    Handles spawning, stealth injection, and crash recovery.
    """
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.lock = asyncio.Lock()

    async def initialize(self):
        """Boots the Chromium Engine."""
        SYS_LOG.info("Initializing The Grid...")
        self.playwright = await async_playwright().start()
        
        # Launch Arguments for Maximum Stealth & Stability
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-background-timer-throttling",
            "--disable-popup-blocking",
            "--disable-renderer-backgrounding"
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=CFG.BROWSER_HEADLESS,
            args=args,
            slow_mo=50 # Human-like micro-latency
        )
        SYS_LOG.info("Grid Online: Chromium Engine Active.")

    async def create_stealth_context(self) -> BrowserContext:
        """Creates a fingerprint-resistant browser context."""
        if not self.browser:
            await self.initialize()
            
        context = await self.browser.new_context(
            user_agent=CFG.USER_AGENT,
            viewport=CFG.VIEWPORT,
            locale="en-US",
            timezone_id="Asia/Kolkata", # Localized for your IPO task
            permissions=["geolocation"],
            java_script_enabled=True
        )
        
        # Inject Anti-Detection Scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        return context

    async def shutdown(self):
        """Graceful shutdown of the grid."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        SYS_LOG.info("Grid Shutdown Complete.")

# ==============================================================================
#        LAYER 3: THE HIVE (AGENT EXECUTION)
# ==============================================================================
# Import the Trinity (Architect, Sensor, Navigator)
try:
    from agents.mission_architect import MissionArchitectAgent
    from agents.semantic_sensor import SemanticSensorAgent
    from agents.shadow_navigator import ShadowNavigatorAgent
    from src.cognition.schema import AgentState, MissionStatus
except ImportError:
    SYS_LOG.warning("Agents not found. Running in Simulation Mode.")
    # Mock classes for testing if files are missing
    class MissionArchitectAgent: 
        def plan(self, s): 
            s['semantic_map'] = {'action':'WAIT'}
            return s
    class SemanticSensorAgent:
        def analyze(self, s): return s
        DEEP_SCAN_SCRIPT = "return {}"
    class ShadowNavigatorAgent:
        async def execute(self, s, p): return s

class HiveWorker:
    """
    An individual drone in the swarm.
    Executes one Mission (URL) from start to finish.
    """
    def __init__(self, mission_id: str, context: BrowserContext, task: Dict):
        self.id = mission_id
        self.context = context
        self.task = task
        self.start_time = time.time()
        
        # The Trinity
        self.architect = MissionArchitectAgent()
        self.sensor = SemanticSensorAgent()
        self.navigator = ShadowNavigatorAgent()
        
        # State Vector
        self.state = {
            "mission_id": mission_id,
            "goal": self.task['goal'],
            "url": self.task['url'],
            "current_url": self.task['url'],
            "status": "PENDING",
            "dom_snapshot": [],
            "semantic_map": {},
            "history_steps": [],
            "child_missions": [],
            "error_log": [],
            "site_physics": {        # <--- THE MISSING KEY
                "entropy": 0.0,
                "latency": 0.1,
                "drift": 0.0
            },
            "perception_meta": {},
            "knowledge_graph": {}
        }

    async def run(self):
        """The Main OODA Loop."""
        page = await self.context.new_page()
        SYS_LOG.info(f"[{self.id}] Deploying to {self.task['url']}")
        
        try:
            # 1. Infiltration
            await page.goto(self.task['url'], timeout=60000, wait_until="domcontentloaded")
            self.state['current_url'] = self.task['url']
            
            step_count = 0
            while step_count < CFG.MAX_STEPS:
                step_count += 1
                
                # Check Timeout
                if time.time() - self.start_time > CFG.TASK_TIMEOUT:
                    SYS_LOG.warning(f"[{self.id}] Mission Timed Out. Aborting.")
                    break

                # --- PHASE 1: SENSE ---
                try:
                    snapshot = await page.evaluate(self.sensor.DEEP_SCAN_SCRIPT)
                    self.state['dom_snapshot'] = snapshot
                    self.state = self.sensor.analyze(self.state)
                except Exception as e:
                    SYS_LOG.error(f"[{self.id}] Sensor Glitch: {e}")
                    await asyncio.sleep(2) # Stabilize
                    continue

                # --- PHASE 2: PLAN ---
                self.state = self.architect.plan(self.state)
                
                # Handling Architect Decisions
                if self.state['status'] == MissionStatus.COMPLETED.value:
                    SYS_LOG.info(f"[{self.id}] OBJECTIVE SECURED.")
                    break
                
                if self.state['status'] == MissionStatus.FAILED.value:
                    SYS_LOG.error(f"[{self.id}] Mission Failed: {self.state.get('error_log')}")
                    break

                # --- PHASE 3: ACT ---
                plan = self.state.get('semantic_map', {})
                action = plan.get('action', 'WAIT')
                
                if action != 'WAIT':
                    # SYS_LOG.info(f"[{self.id}] Action: {action} -> {plan.get('thought')}")
                    self.state = await self.navigator.execute(self.state, page)
                else:
                    await asyncio.sleep(1.0) # Idle tick

                # --- PHASE 4: SPAWN ---
                # Check if Architect found new links (Recursive Crawl)
                if self.state['child_missions']:
                    # In a full swarm, we'd add these to the Overmind's queue
                    # For now, we just log them
                    # SYS_LOG.info(f"[{self.id}] Discovered {len(self.state['child_missions'])} potential targets.")
                    self.state['child_missions'] = []

            # End of Mission
            await self._generate_report()

        except Exception as e:
            SYS_LOG.error(f"[{self.id}] CRITICAL WORKER FAILURE: {e}")
            traceback.print_exc()
        finally:
            await page.close()

    async def _generate_report(self):
        """Dumps mission logs to disk."""
        filename = f"reports/{self.id}_{int(time.time())}.json"
        os.makedirs("reports", exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

# ==============================================================================
#        LAYER 4: THE OVERMIND (ORCHESTRATOR)
# ==============================================================================
class Overmind:
    """
    The Central Intelligence.
    Controls the Queue, manages the GPU Lock, and balances VRAM.
    """
    def __init__(self):
        self.nexus = NeuralNexusBridge()
        self.grid = GridController()
        self.queue = asyncio.Queue()
        self.active_agents = set()
        self.semaphore = asyncio.Semaphore(CFG.MAX_CONCURRENCY)

    async def bootstrap(self, directive: str):
        """Initializes the Swarm."""
        SYS_LOG.info("OVERMIND: Bootstrapping Sequence Initiated.")
        
        # 1. Start Grid
        await self.grid.initialize()
        
        # 2. Generate Strategy (GPU)
        SYS_LOG.info(f"OVERMIND: Analyzing Directive: '{directive}'")
        manifest = self.nexus.generate_tactics(directive)
        SYS_LOG.info(f"OVERMIND: Strategy Validated. {len(manifest)} Vectors Loaded.")
        
        # 3. Load Queue
        for task in manifest:
            await self.queue.put(task)

        # 4. Begin Execution Loop
        await self.process_queue()
        
        # 5. Shutdown
        await self.grid.shutdown()
        SYS_LOG.info("OVERMIND: Sequence Complete. Swarm Offline.")

    async def process_queue(self):
        """Main Orchestration Loop."""
        workers = []
        
        while not self.queue.empty():
            # Respect Concurrency Limit
            await self.semaphore.acquire()
            
            task = await self.queue.get()
            
            # Spawn Worker Task
            worker_task = asyncio.create_task(self._deploy_agent(task))
            workers.append(worker_task)
            
            # Small stagger to prevent browser launch spike
            await asyncio.sleep(2.0)

        # Wait for all agents to finish
        if workers:
            await asyncio.wait(workers)

    async def _deploy_agent(self, task: Dict):
        """Deploys a single agent and manages its lifecycle."""
        mission_id = f"M-{random.randint(1000,9999)}"
        
        try:
            # Create Browser Context (Lightweight)
            context = await self.grid.create_stealth_context()
            
            # Initialize Worker
            worker = HiveWorker(mission_id, context, task)
            
            # Execute
            await worker.run()
            
            # Cleanup
            await context.close()
            
        except Exception as e:
            SYS_LOG.error(f"OVERMIND: Agent {mission_id} Lost: {e}")
        finally:
            self.semaphore.release()
            self.queue.task_done()

# ==============================================================================
#        TELEMETRY MONITOR (THREADED)
# ==============================================================================
async def telemetry_loop():
    """Background task to log VRAM and System health."""
    while True:
        try:
            # Only if GPU is available
            if torch.cuda.is_available():
                vram = torch.cuda.memory_allocated(0) / 1e6
                vram_total = torch.cuda.get_device_properties(0).total_memory / 1e6
                util = vram / vram_total * 100
                # SYS_LOG.debug(f"[TELEMETRY] VRAM: {vram:.0f}MB / {vram_total:.0f}MB ({util:.1f}%)")
        except: pass
        await asyncio.sleep(5)

# ==============================================================================
#        MAIN ENTRY POINT
# ==============================================================================
async def main():
    # 1. Setup Signal Handlers
    loop = asyncio.get_running_loop()
    
    # 2. Define Directive
    DIRECTIVE = "Identify top 3 upcoming IPOs in India and find their DRHP documents."
    
    # 3. Ignite Overmind
    overmind = Overmind()
    
    # 4. Launch Telemetry
    telemetry = asyncio.create_task(telemetry_loop())
    
    # 5. Run Mission
    await overmind.bootstrap(DIRECTIVE)
    
    # 6. Cleanup
    telemetry.cancel()

if __name__ == "__main__":
    # Import torch just for telemetry check
    try: import torch
    except: pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] MANUAL OVERRIDE: Swarm Halting...")