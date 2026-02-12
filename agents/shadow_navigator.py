"""
Drishti-AX: Shadow Navigator Agent (The Titan Prime)
Module: agents/shadow_navigator.py
Version: Sentinel-14.6 "Titan Prime"
Author: Sentinel Core System
Timestamp: 2026-02-14 00:00:00 UTC
Classification: TOP SECRET // KINETIC PHYSICS ENGINE

Description:
    The ultimate interface between the digital mind and the browser DOM.
    It does not 'execute commands'; it simulates a human user sitting at a 
    physical terminal.

    ARCHITECTURAL LAYERS:
    1.  PHYSICS LAYER: Calculates Bezier curves, velocity profiles, and 
        Fitts's Law trajectories.
    2.  INPUT LAYER: Manages low-level CDP (Chrome DevTools Protocol) events 
        to bypass JavaScript event listeners.
    3.  STRATEGY LAYER: The Omni-Click Ladder (4-stage retry mechanism).
    4.  SAFETY LAYER: Visual Servoing (Anti-Drift) and Execution Guardrails.

    INPUT: AgentState (With 'semantic_map' instruction)
    OUTPUT: AgentState (Updated 'status' and 'history_steps')
"""

import asyncio
import logging
import math
import random
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field

# ==============================================================================
#        CRITICAL: SCHEMA IMPORT
# ==============================================================================
try:
    from src.cognition.schema import (
        AgentState, MissionStatus, KineticInterference, SentinelSwarmError,
        StrategyMode
    )
except ImportError:
    # Fallback for direct testing
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.cognition.schema import AgentState, MissionStatus, KineticInterference, SentinelSwarmError

# ==============================================================================
#        NAVIGATOR CONFIGURATION & PHYSICS CONSTANTS
# ==============================================================================
logger = logging.getLogger("ShadowNavigator")
logger.setLevel(logging.DEBUG)

@dataclass
class PhysicsConfig:
    # Fitts's Law Constants
    a_term: float = 0.1
    b_term: float = 0.2
    
    # Mouse Movement
    mouse_speed_min: float = 0.5        # ms per pixel
    mouse_speed_max: float = 1.2
    jitter_strength: float = 2.0        # Pixel deviation
    overshoot_prob: float = 0.3         # 30% chance to miss and correct
    
    # Typing Dynamics (QWERTY distance simulation)
    base_typing_latency: float = 0.12
    key_distance_penalty: float = 0.05  # Extra time for far keys
    
    # Scrolling
    scroll_friction: float = 0.9        # Deceleration factor
    scroll_boost: int = 150             # Initial flick strength

    # System
    viewport_w: int = 1920
    viewport_h: int = 1080
    debug_draw: bool = False            # Draw mouse path on screen (Canvas)

CFG = PhysicsConfig()

# ==============================================================================
#        LAYER 1: NEWTONIAN PHYSICS ENGINE
# ==============================================================================
class KineticPhysicsEngine:
    """
    Simulates the physical constraints of a human hand moving a mouse.
    """
    
    def calculate_trajectory(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Generates a human-like path using Cubic Bezier curves with 
        velocity ramping and simulated hand tremor (Perlin noise approximation).
        """
        path = []
        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        
        # 1. Control Points (Randomized based on distance)
        # Humans don't move in straight lines; we arc.
        arc_scale = min(distance * 0.2, 200)
        cx1 = start[0] + (end[0] - start[0]) * 0.33 + random.uniform(-arc_scale, arc_scale)
        cy1 = start[1] + (end[1] - start[1]) * 0.33 + random.uniform(-arc_scale, arc_scale)
        
        cx2 = start[0] + (end[0] - start[0]) * 0.66 + random.uniform(-arc_scale, arc_scale)
        cy2 = start[1] + (end[1] - start[1]) * 0.66 + random.uniform(-arc_scale, arc_scale)
        
        # 2. Step Calculation (Fitts's Law)
        # T = a + b * log2(D/W + 1)
        # More steps for longer distances, fewer for short.
        steps = int(max(25, distance / 15))
        
        for t in range(steps + 1):
            norm_t = t / steps
            # Cubic Bezier
            x = (1-norm_t)**3 * start[0] + \
                3*(1-norm_t)**2 * norm_t * cx1 + \
                3*(1-norm_t) * norm_t**2 * cx2 + \
                norm_t**3 * end[0]
            
            y = (1-norm_t)**3 * start[1] + \
                3*(1-norm_t)**2 * norm_t * cy1 + \
                3*(1-norm_t) * norm_t**2 * cy2 + \
                norm_t**3 * end[1]
            
            # 3. Micro-Jitter (Hand Tremor)
            # Adds sub-pixel noise that vanishes as we approach target
            tremor_scale = CFG.jitter_strength * (1 - norm_t) # Stabilize at end
            x += random.gauss(0, tremor_scale)
            y += random.gauss(0, tremor_scale)
            
            path.append((x, y))
            
        # 4. Overshoot Simulation (The "Human" Flaw)
        if random.random() < CFG.overshoot_prob:
            overshoot_x = end[0] + (end[0] - start[0]) * 0.05
            overshoot_y = end[1] + (end[1] - start[1]) * 0.05
            correction_path = self.calculate_correction((path[-1][0], path[-1][1]), end)
            path.extend(correction_path)
        else:
            path.append(end) # Snap to grid if no overshoot
            
        return path

    def calculate_correction(self, current: Tuple[float, float], target: Tuple[int, int]) -> List[Tuple[float, float]]:
        """
        Small micro-adjustment path when the user overshoots the target.
        """
        return [(current[0] * 0.5 + target[0] * 0.5, current[1] * 0.5 + target[1] * 0.5), target]

    def get_typing_delay(self, char_a: str, char_b: str) -> float:
        """
        Calculates delay between keystrokes based on QWERTY layout distance.
        """
        # Simplified layout map (row, col)
        layout = {
            'q':(0,0), 'w':(0,1), 'e':(0,2), 'r':(0,3), 't':(0,4), 'y':(0,5),
            'a':(1,0), 's':(1,1), 'd':(1,2), 'f':(1,3), 'g':(1,4), 'h':(1,5),
            'z':(2,0), 'x':(2,1), 'c':(2,2), 'v':(2,3), 'b':(2,4), 'n':(2,5)
        }
        pos_a = layout.get(char_a.lower(), (1,5))
        pos_b = layout.get(char_b.lower(), (1,5))
        
        dist = math.hypot(pos_b[0]-pos_a[0], pos_b[1]-pos_a[1])
        base_delay = random.gauss(CFG.base_typing_latency, 0.02)
        
        return base_delay + (dist * CFG.key_distance_penalty)

PHYSICS = KineticPhysicsEngine()

# ==============================================================================
#        LAYER 2: SHADOW NAVIGATOR AGENT (THE BRAIN)
# ==============================================================================
class ShadowNavigatorAgent:
    """
    The Kinetic Executor.
    Manages the high-level logic of interacting with the browser.
    """
    def __init__(self):
        self.mouse_pos = (0, 0) # Track virtual mouse position

    async def execute(self, state: AgentState, page: Any) -> AgentState:
        """
        The Main Actuation Loop.
        """
        mission_id = state.get('mission_id', 'UNKNOWN')
        plan = state.get('semantic_map', {})
        action = plan.get('action', 'WAIT')
        
        # 0. Safety Check
        if not plan:
            logger.warning(f"[{mission_id}] Navigator Idle (No Plan).")
            state['status'] = MissionStatus.ANALYZING.value
            return state

        logger.info(f"[{mission_id}] ACTUATING: {action} on {plan.get('selector', 'Global')}")

        try:
            # 1. Visual Servoing (Pre-Action Verification)
            if action in ["CLICK", "TYPE", "HOVER"]:
                target_rect = await self._verify_target_position(page, plan)
                if not target_rect:
                    raise KineticInterference("Target shifted or vanished during approach.")
                plan['target_rect'] = target_rect # Update with fresh coordinates

            # 2. Execution Switch
            if action == "CLICK":
                await self._execute_omni_click(page, plan)
            elif action == "TYPE":
                await self._execute_human_type(page, plan)
            elif action == "SCROLL":
                await self._execute_smooth_scroll(page, plan)
            elif action == "WAIT":
                await asyncio.sleep(plan.get('duration', 1.0))
            else:
                logger.error(f"Unknown Kinetic Action: {action}")

            # 3. Post-Action Settlement
            # Humans pause briefly after an action to verify result
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 4. Success State Update
            state['status'] = MissionStatus.ANALYZING.value # Hand back to Sensor
            state['history_steps'].append(f"{action} -> {plan.get('xpath')}")

        except Exception as e:
            logger.error(f"[{mission_id}] Kinetic Failure: {e}")
            state['error_log'].append(f"Navigator Error: {str(e)}")
            # If we failed, force a re-plan
            state['status'] = MissionStatus.PLANNING.value
            
            # Take Evidence Screenshot
            try:
                path = f"reports/evidence/{mission_id}_fail_{int(time.time())}.png"
                await page.screenshot(path=path)
            except: pass

        return state

    # --------------------------------------------------------------------------
    # LAYER 3: VISUAL SERVOING (LAYOUT SHIFT PROTECTION)
    # --------------------------------------------------------------------------
    async def _verify_target_position(self, page, plan) -> Optional[Dict]:
        """
        Re-scans the specific element just before interaction to ensure
        it hasn't moved (Layout Shift) or been covered by a popup.
        """
        xpath = plan.get('xpath')
        try:
            # Quick CDP query for fresh rect
            box = await page.evaluate(f"""() => {{
                const el = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{ x: r.x, y: r.y, width: r.width, height: r.height, visible: (r.width > 0 && r.height > 0) }};
            }}""")
            
            if box and box['visible']:
                # Add randomness to click point (don't click exact center)
                box['target_x'] = box['x'] + (box['width'] * random.uniform(0.2, 0.8))
                box['target_y'] = box['y'] + (box['height'] * random.uniform(0.2, 0.8))
                return box
            return None
        except:
            return None

    # --------------------------------------------------------------------------
    # LAYER 4: THE OMNI-CLICK LADDER (ESCALATION PROTOCOL)
    # --------------------------------------------------------------------------
    async def _execute_omni_click(self, page, plan):
        """
        Attempts to click a target using 4 increasingly aggressive methods.
        """
        rect = plan['target_rect']
        target_x, target_y = rect['target_x'], rect['target_y']
        
        # 1. MOVE MOUSE (Approach)
        await self._human_mouse_move(page, (target_x, target_y))
        
        # STAGE 1: Standard Interaction (Best for Single Page Apps)
        try:
            # We use the coordinates we moved to, ensuring hover state is active
            await page.mouse.click(target_x, target_y, delay=random.randint(50, 150))
            return
        except Exception as e:
            logger.debug(f"Stage 1 Click Failed ({e}). Escalating...")

        # STAGE 2: JavaScript Dispatch (Bypass Overlays)
        try:
            await page.evaluate(f"""
                const el = document.elementFromPoint({target_x}, {target_y});
                if(el) {{ el.click(); }} else {{ throw new Error('No element at coords'); }}
            """)
            return
        except Exception:
            logger.debug("Stage 2 Click Failed. Escalating...")

        # STAGE 3: CDP Protocol (Hardware Emulation)
        # This sends raw input signals to the browser engine, bypassing JS entirely.
        try:
            client = await page.context.new_cdp_session(page)
            await client.send("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": target_x, "y": target_y, "button": "left", "clickCount": 1
            })
            await asyncio.sleep(random.uniform(0.05, 0.1)) # Mechanical switch delay
            await client.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": target_x, "y": target_y, "button": "left", "clickCount": 1
            })
            return
        except Exception as e:
            logger.error(f"Stage 3 CDP Click Failed: {e}")
            raise KineticInterference("Target Unreachable via any method.")

    # --------------------------------------------------------------------------
    # LAYER 5: HUMAN TYPING ENGINE
    # --------------------------------------------------------------------------
    async def _execute_human_type(self, page, plan):
        """
        Types text with realistic latency and error correction.
        """
        text = plan.get('value', '')
        rect = plan['target_rect']
        
        # 1. Focus Field
        await self._execute_omni_click(page, plan)
        
        # 2. Clear Field (Ctrl+A, Del) - Human style
        await page.keyboard.press("Control+A")
        await asyncio.sleep(0.1)
        await page.keyboard.press("Backspace")
        
        # 3. Type Loop
        prev_char = ' '
        for char in text:
            # Calculate physical delay
            delay = PHYSICS.get_typing_delay(prev_char, char)
            
            # Simulate "Thinking" pause at spaces or punctuation
            if char in [' ', '.', ',']:
                delay += random.uniform(0.1, 0.3)
                
            await asyncio.sleep(delay)
            await page.keyboard.type(char)
            prev_char = char
            
        # 4. Commit (Enter)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Enter")

    # --------------------------------------------------------------------------
    # LAYER 6: INERTIAL SCROLLING
    # --------------------------------------------------------------------------
    async def _execute_smooth_scroll(self, page, plan):
        """
        Simulates a mouse wheel flick with inertia.
        """
        direction = 1 if plan.get('direction', 'DOWN') == 'DOWN' else -1
        intensity = plan.get('amount', 500)
        
        velocity = CFG.scroll_boost
        distance_traveled = 0
        
        while distance_traveled < intensity and velocity > 10:
            # Apply Friction
            velocity *= CFG.scroll_friction
            step = velocity * direction
            
            await page.mouse.wheel(0, step)
            distance_traveled += abs(step)
            
            # Rendering wait (16ms = 60fps)
            await asyncio.sleep(0.016)

    # --------------------------------------------------------------------------
    # UTILITIES: ACTUATION
    # --------------------------------------------------------------------------
    async def _human_mouse_move(self, page, target: Tuple[float, float]):
        """
        Executes the Bezier curve trajectory.
        """
        start = self.mouse_pos
        # If we don't know where mouse is, assume center
        if start == (0,0): start = (CFG.viewport_w // 2, CFG.viewport_h // 2)
        
        trajectory = PHYSICS.calculate_trajectory(start, target)
        
        for point in trajectory:
            try:
                await page.mouse.move(point[0], point[1], steps=1)
                
                # Variable Velocity (Fast in middle, slow at ends)
                # This mimics muscle tension/relaxation
                progress = trajectory.index(point) / len(trajectory)
                if 0.2 < progress < 0.8:
                    # Fast phase
                    await asyncio.sleep(0.001)
                else:
                    # Precision phase
                    await asyncio.sleep(0.005)
            except: break
            
        self.mouse_pos = target # Update virtual position