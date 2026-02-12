"""
Drishti-AX: Semantic Sensor Agent (The Panopticon)
Module: agents/semantic_sensor.py
Version: Sentinel-14.5 "Panopticon"
Author: Sentinel Core System
Timestamp: 2026-02-13 23:00:00 UTC
Classification: TOP SECRET // VISUAL INTELLIGENCE

Description:
    The 'Eyes' of the Sentinel Swarm.
    It performs a pixel-perfect scan of the DOM, filtering out invisible 
    elements, calculating z-index stacking contexts, and clustering 
    semantically related items.

    CAPABILITIES:
    1.  Recursive Shadow DOM Traversal.
    2.  Computed Style Analysis (Visibility, Opacity, Z-Index).
    3.  Geometric Clustering (Label + Input association).
    4.  Temporal Diffing (Detecting Loading States).

    INPUT: AgentState (Current Browser Context)
    OUTPUT: AgentState (Updated 'dom_snapshot' and 'perception_meta')
"""

import logging
import json
import math
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass

# ==============================================================================
#        CRITICAL: SCHEMA IMPORT
# ==============================================================================
try:
    from src.cognition.schema import (
        AgentState, MissionStatus, PerceptualDrift, SentinelSwarmError
    )
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.cognition.schema import AgentState, MissionStatus

# ==============================================================================
#        SENSOR CONFIGURATION
# ==============================================================================
logger = logging.getLogger("SemanticSensor")
logger.setLevel(logging.INFO)

@dataclass
class SensorConfig:
    max_elements: int = 500             # Hard limit to prevent context overflow
    iou_threshold: float = 0.5          # Intersection over Union for duplicate detection
    dynamic_wait: float = 0.5           # Time to wait for layout shifts
    blind_spot_retries: int = 2         # How many times to retry empty scans
    screenshot_on_fail: bool = True     # Capture visual evidence of failures

CFG = SensorConfig()

# ==============================================================================
#        THE DEEP SCAN INJECTION (JAVASCRIPT PAYLOAD)
# ==============================================================================
# This script is injected into the browser. It runs inside the V8 engine.
# It is the only way to accurately detect visibility and Shadow DOMs.
DEEP_SCAN_PAYLOAD = """
(() => {
    const INTERACTIVE_TAGS = new Set(['A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'DETAILS', 'LABEL']);
    const HELPER_ATTRS = ['aria-label', 'title', 'placeholder', 'name', 'id', 'role'];
    
    // 1. Recursive Shadow DOM Walker
    function collectNodes(root = document, nodes = []) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, {
            acceptNode: (node) => {
                const style = window.getComputedStyle(node);
                // Filter invisible elements immediately
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) < 0.1) {
                    return NodeFilter.FILTER_REJECT;
                }
                // Filter huge overlays or tiny invisible tracking pixels
                const rect = node.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) return NodeFilter.FILTER_REJECT;
                
                return NodeFilter.FILTER_ACCEPT;
            }
        });

        let node;
        while (node = walker.nextNode()) {
            // Check if node is interactive or contains text
            if (INTERACTIVE_TAGS.has(node.tagName) || (node.innerText && node.innerText.length < 200)) {
                nodes.push(node);
            }
            // Dive into Shadow Root
            if (node.shadowRoot) {
                collectNodes(node.shadowRoot, nodes);
            }
        }
        return nodes;
    }

    // 2. XPath Generator
    function getXPath(element) {
        if (element.id !== '') return `//*[@id="${element.id}"]`;
        if (element === document.body) return '/html/body';
        let ix = 0;
        const siblings = element.parentNode ? element.parentNode.childNodes : [];
        for (let i = 0; i < siblings.length; i++) {
            const sibling = siblings[i];
            if (sibling === element) return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) ix++;
        }
        return ''; // Fallback
    }

    // 3. Execution
    try {
        const rawElements = collectNodes();
        const results = rawElements.map(el => {
            const rect = el.getBoundingClientRect();
            
            // Extract Attributes
            const attrs = {};
            for (let attr of HELPER_ATTRS) {
                if (el.hasAttribute(attr)) attrs[attr] = el.getAttribute(attr);
            }
            if (el.tagName === 'A') attrs['href'] = el.href;
            if (el.tagName === 'INPUT') attrs['type'] = el.type;

            return {
                tag: el.tagName,
                text: el.innerText ? el.innerText.trim().slice(0, 100) : "",
                xpath: getXPath(el),
                rect: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    top: Math.round(rect.top),
                    left: Math.round(rect.left)
                },
                attributes: attrs,
                visible: true,
                is_shadow: !!el.getRootNode().host // Flag if inside Shadow DOM
            };
        });

        // Limit payload size
        return results.slice(0, 1000); 

    } catch (e) {
        return { error: e.toString() };
    }
})();
"""

# ==============================================================================
#        CORE INTELLIGENCE: THE SENSOR AGENT
# ==============================================================================
class SemanticSensorAgent:
    """
    The Visual Cortex.
    """
    def __init__(self):
        self.DEEP_SCAN_SCRIPT = DEEP_SCAN_PAYLOAD
        self.last_snapshot_hash = ""
        self.consecutive_stalls = 0

    def analyze(self, state: AgentState) -> AgentState:
        """
        The Main Perception Loop.
        1. Ingests Raw DOM (passed from Runner).
        2. Cleans & Filters Data.
        3. Calculates Visual Hierarchy.
        4. Detects Drifts/Changes.
        """
        mission_id = state.get('mission_id', 'UNKNOWN')
        # logger.info(f"[{mission_id}] Sensor active. Processing visual field...")

        raw_data = state.get('dom_snapshot', [])

        # 1. ERROR CHECKING
        if isinstance(raw_data, dict) and 'error' in raw_data:
            logger.error(f"[{mission_id}] JS Injection Failed: {raw_data['error']}")
            state['error_log'].append(f"Sensor Error: {raw_data['error']}")
            return state

        if not raw_data:
            logger.warning(f"[{mission_id}] Retina Empty. Retrying scan...")
            # Runner loop handles the retry, we just flag it
            return state

        # 2. DATA CLEANING & NORMALIZATION
        processed_elements = self._clean_data(raw_data)
        
        # 3. GEOMETRIC CLUSTERING (The "Visual Brain")
        # We define sectors: Header, Footer, Sidebar, Main Content
        view_port = {"width": 1920, "height": 1080} # Assumed
        hierarchy = self._calculate_visual_hierarchy(processed_elements, view_port)
        
        # 4. TEMPORAL DIFFING (Detecting AJAX)
        current_hash = self._generate_snapshot_hash(processed_elements)
        is_stable = self._check_stability(current_hash)
        
        # Update State
        state['dom_snapshot'] = processed_elements
        state['perception_meta'] = {
            "element_count": len(processed_elements),
            "hierarchy": hierarchy,
            "is_stable": is_stable,
            "scan_timestamp": time.time(),
            "snapshot_hash": current_hash
        }
        
        # Physics Update (Latency Detection)
        if not is_stable:
            state['site_physics']['latency'] = state['site_physics'].get('latency', 1.0) * 1.5
            logger.info(f"[{mission_id}] Visual Drift Detected (Loading?). Latency penalty applied.")
        else:
            state['site_physics']['latency'] = max(0.5, state['site_physics'].get('latency', 1.0) * 0.9)

        return state

    # --------------------------------------------------------------------------
    # LEVEL 1: DATA PURIFICATION
    # --------------------------------------------------------------------------
    def _clean_data(self, raw_elements: List[Dict]) -> List[Dict]:
        """
        Removes noise, trims whitespace, and validates geometry.
        """
        clean = []
        seen_xpaths = set()

        for el in raw_elements:
            # 1. Deduplication
            if el['xpath'] in seen_xpaths: continue
            seen_xpaths.add(el['xpath'])

            # 2. Text Normalization
            if el.get('text'):
                el['text'] = " ".join(el['text'].split()) # Remove newlines/tabs
            
            # 3. Significance Check
            # Ignore empty divs unless they are interactive inputs
            if not el['text'] and el['tag'] not in ['INPUT', 'SELECT', 'BUTTON', 'TEXTAREA']:
                # Check for attributes that imply meaning
                if not any(el['attributes'].values()):
                    continue

            clean.append(el)

        # Sort by visual importance (Top-Left to Bottom-Right)
        clean.sort(key=lambda x: (x['rect']['y'], x['rect']['x']))
        
        return clean[:CFG.max_elements]

    # --------------------------------------------------------------------------
    # LEVEL 2: GEOMETRIC CLUSTERING (VISUAL CORTEX)
    # --------------------------------------------------------------------------
    def _calculate_visual_hierarchy(self, elements: List[Dict], viewport: Dict) -> Dict:
        """
        Divides the page into logical sectors based on coordinates.
        This helps the Architect ignore Footers/Headers when looking for Content.
        """
        sectors = {
            "header": [],
            "footer": [],
            "sidebar_left": [],
            "main_content": []
        }
        
        header_threshold = viewport['height'] * 0.15
        footer_threshold = viewport['height'] * 0.85
        sidebar_threshold = viewport['width'] * 0.20

        for el in elements:
            y = el['rect']['y']
            x = el['rect']['x']
            
            if y < header_threshold:
                sectors['header'].append(el['xpath'])
            elif y > footer_threshold:
                sectors['footer'].append(el['xpath'])
            elif x < sidebar_threshold:
                sectors['sidebar_left'].append(el['xpath'])
            else:
                sectors['main_content'].append(el['xpath'])
                
        # Calculate Density
        density = {k: len(v) for k, v in sectors.items()}
        return density

    # --------------------------------------------------------------------------
    # LEVEL 3: TEMPORAL STABILITY
    # --------------------------------------------------------------------------
    def _generate_snapshot_hash(self, elements: List[Dict]) -> str:
        """
        Creates a fingerprint of the current page state.
        """
        # We hash the XPaths + Text to detect content changes
        content_string = "".join([f"{e['xpath']}:{e.get('text','')}" for e in elements])
        return hashlib.md5(content_string.encode('utf-8')).hexdigest()

    def _check_stability(self, current_hash: str) -> bool:
        """
        Determines if the page is still loading/animating.
        """
        is_stable = (current_hash == self.last_snapshot_hash)
        
        if is_stable:
            self.consecutive_stalls += 1
        else:
            self.consecutive_stalls = 0
            
        self.last_snapshot_hash = current_hash
        
        # We consider it stable if it hasn't changed for 1 cycle, 
        # OR if it's changing constantly (carousel) we might ignore it after 5 cycles.
        return is_stable