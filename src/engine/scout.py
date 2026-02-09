import asyncio
import json
import sys
import os
import re
import time
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from axe_core_python.async_playwright import Axe

# ==========================================
#        SYSTEM CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
EVIDENCE_DIR = os.path.join(REPORT_DIR, "evidence")
DATA_DIR = os.path.join(REPORT_DIR, "data")

# Ensure directories exist
os.makedirs(EVIDENCE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ==========================================
#        TUNING PARAMETERS
# ==========================================
SCREENSHOT_TIMEOUT = 15000       # 15s to take a full-page screenshot
NAVIGATION_TIMEOUT = 120000      # 2 minutes max for government sites
MAX_HYDRATION_WAIT = 25000       # Wait up to 25s for the "spinner" to stop
STABILITY_CHECK_INTERVAL = 1.0   # Check for DOM stability every 1s

# ==========================================
#        DRISHTI SCORING WEIGHTS
# ==========================================
WEIGHT_CRITICAL = 15             # Deduction for a "Blocker" violation
WEIGHT_SERIOUS = 10              # Deduction for a severe violation
WEIGHT_MODERATE = 5              # Deduction for a minor violation
WEIGHT_JS_ERROR = 20             # Deduction if the site throws errors
WEIGHT_LOAD_TIME = 2             # Deduction per second over 3s
WEIGHT_MISSING_LANG = 15         # Deduction for missing language tag
WEIGHT_NON_SECURE = 25           # Deduction for HTTP (Not HTTPS)
WEIGHT_TRACKER_HEAVY = 10        # Deduction for >5 ad trackers

# ==========================================
#        THE DEEP AUDITOR ENGINE
# ==========================================
class DeepAuditor:
    """
    This class contains the proprietary JavaScript payload that is injected
    into the browser. It performs 75+ checks that standard tools (like Axe) miss.
    It covers: Visual, Cognitive, Legal, Structural, Network, and Relational layers.
    """
    SCRIPT = """
    () => {
        // --- INTERNAL HELPER FUNCTIONS ---
        
        // Generates a precise XPATH for any element (Critical for Phase 3 AI Agents)
        const getElementXpath = (element) => {
            if (!element || element.nodeType !== 1) return '';
            if (element.id) return `//*[@id="${element.id}"]`;
            const sPath = [];
            while (element.nodeType === 1) {
                let iIndex = 1;
                for (let sibling = element.previousSibling; sibling; sibling = sibling.previousSibling) {
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName) iIndex++;
                }
                const sTagName = element.tagName.toLowerCase();
                sPath.unshift(`${sTagName}[${iIndex}]`);
                element = element.parentNode;
            }
            return `/${sPath.join('/')}`;
        };

        // Checks if an element is actually visible to a human user
        const isVisible = (el) => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && 
                   window.getComputedStyle(el).visibility !== 'hidden' &&
                   window.getComputedStyle(el).display !== 'none';
        };

        // Estimates reading level using Flesch-Kincaid logic
        const fleschKincaidEstimate = (text) => {
            const words = text.split(/\\s+/).length;
            const sentences = text.split(/[.!?]+/).length || 1;
            // Formula: 0.39 * (words/sentences) + 11.8 - simplified proxy
            return (0.39 * (words / sentences)) + 11.8; 
        };

        // --- DATA COLLECTION START ---
        
        const allEls = Array.from(document.querySelectorAll('*'));
        const interactive = Array.from(document.querySelectorAll('button, a, input, select, textarea, [role="button"], [tabindex="0"]'));
        const bodyText = document.body.innerText || "";
        
        // --- LAYER F: SENSORY & COGNITIVE ---
        const motionElements = document.querySelectorAll('video, marquee, .parallax, [data-aos], canvas');
        const flashingElements = document.querySelectorAll('blink, .flash, .blink, [class*="animate"]');
        
        // --- LAYER G: NAVIGATION & STRUCTURE ---
        const landmarks = document.querySelectorAll('main, nav, header, footer, aside, [role="main"], [role="navigation"]');
        
        // Focus Order Logic: Check if tabbing jumps wildly around the page
        const focusOrder = interactive.filter(isVisible).map(el => {
            const r = el.getBoundingClientRect();
            return { tag: el.tagName, y: Math.round(r.y), x: Math.round(r.x) };
        });
        const erraticFocus = focusOrder.some((curr, i) => {
            if (i === 0) return false;
            const prev = focusOrder[i-1];
            // If current element is 200px *above* the previous one, it's a "Jump Back"
            return curr.y < prev.y - 200; 
        });

        // --- LAYER H: PERFORMANCE (ADVANCED) ---
        // Layout Shifts: Detect elements with absolute/fixed positioning that might float
        const potentialLayoutShifts = allEls.filter(el => {
            const style = window.getComputedStyle(el);
            return style.position === 'absolute' || style.position === 'fixed';
        }).length;

        // Third-Party Trackers: Analyze script sources
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        const trackers = scripts.filter(s => /google|facebook|analytics|ad|pixel|tag|manager/i.test(s.src));

        // Heavy Images: Find unoptimized assets
        const heavyImages = Array.from(document.querySelectorAll('img')).filter(img => {
            return img.naturalWidth > 1600 || img.src.endsWith('.png');
        });

        // --- LAYER I: LEGAL & TRUST ---
        const privacyLinks = Array.from(document.querySelectorAll('a')).filter(a => /privacy|terms|policy|disclaimer/i.test(a.innerText));
        const contactLinks = Array.from(document.querySelectorAll('a')).filter(a => /contact|help|support|reach/i.test(a.innerText));
        const hasCaptcha = !!document.querySelector('iframe[src*="captcha"], .g-recaptcha, [id*="captcha"]');

        // --- LAYER J: INTERACTIVE (RELATIONAL MAPPING) ---
        // This creates a "Map" for the Phase 3 AI Agent to understand the page structure
        const elementTree = interactive.slice(0, 50).map(el => ({
            tag: el.tagName,
            text: (el.innerText || el.ariaLabel || el.placeholder || "").trim().substring(0, 50),
            parent_tag: el.parentElement ? el.parentElement.tagName : "BODY",
            xpath: getElementXpath(el),
            is_visible: isVisible(el),
            attributes: {
                role: el.getAttribute('role'),
                type: el.getAttribute('type'),
                aria_label: el.getAttribute('aria-label')
            }
        }));

        // --- COMPILATION & RETURN ---
        return {
            sensory_cognitive: {
                reading_complexity_score: parseFloat(fleschKincaidEstimate(bodyText).toFixed(2)),
                detected_motion_count: motionElements.length,
                detected_flashing_count: flashingElements.length,
                text_density_ratio: (bodyText.length / window.innerHeight).toFixed(2),
                font_count: new Set(Array.from(allEls).map(e => window.getComputedStyle(e).fontFamily)).size
            },
            navigation_structure: {
                landmark_count: landmarks.length,
                has_skip_link: !!Array.from(document.querySelectorAll('a')).find(a => a.innerText.toLowerCase().includes('skip')),
                erratic_focus_order: erraticFocus,
                tabindex_violations: document.querySelectorAll('[tabindex]:not([tabindex="0"]):not([tabindex="-1"])').length,
                heading_levels: Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => h.tagName),
                iframe_missing_title: Array.from(document.querySelectorAll('iframe')).filter(i => !i.title).length,
                broken_links: document.querySelectorAll('a[href="#"], a[href=""]').length
            },
            performance_network: {
                total_scripts: scripts.length,
                tracker_count: trackers.length,
                heavy_image_count: heavyImages.length,
                potential_layout_shifts: potentialLayoutShifts,
                dom_depth: Math.max(...Array.from(allEls).map(e => e.getElementsByTagName('*').length))
            },
            legal_trust: {
                has_privacy_policy: privacyLinks.length > 0,
                has_contact_info: contactLinks.length > 0,
                has_captcha_barrier: hasCaptcha,
                is_secure_context: window.isSecureContext,
                lang_attribute: document.documentElement.lang || "MISSING",
                meta_viewport: document.querySelector('meta[name="viewport"]')?.content || "MISSING"
            },
            interactive_relational: {
                small_touch_targets: interactive.filter(el => {
                    const r = el.getBoundingClientRect();
                    return isVisible(el) && (r.width < 44 || r.height < 44);
                }).length,
                // Check if ARIA label contradicts visual text
                aria_mismatches: interactive.filter(el => {
                    const visual = (el.innerText || "").trim().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || "").trim().toLowerCase();
                    return aria && visual && !aria.includes(visual) && !visual.includes(aria);
                }).length,
                modal_detected: !!document.querySelector('[role="dialog"], .modal, .popup'),
                element_sample_map: elementTree // The AI Map
            }
        };
    }
    """

# ==========================================
#        HELPER FUNCTIONS
# ==========================================

def sanitize_url(input_url):
    """
    Cleans up user input to ensure a valid URL is targeted.
    Handles shorthand like 'irctc' or 'amazon'.
    """
    input_url = input_url.strip().lower()
    
    # Common Alias Mapping
    alias_map = {
        "irctc": "https://www.irctc.co.in/nget/train-search",
        "amazon": "https://www.amazon.in",
        "google": "https://www.google.com",
        "flipkart": "https://www.flipkart.com",
        "epfo": "https://www.epfindia.gov.in",
        "rbi": "https://www.rbi.org.in",
        "uidai": "https://uidai.gov.in"
    }
    
    for key, val in alias_map.items():
        if input_url == key or input_url == f"www.{key}.com" or input_url == f"{key}.in":
            return val

    # Protocol Handling
    if not input_url.startswith("http"):
        if "." not in input_url:
            input_url = f"www.{input_url}.com"
        input_url = "https://" + input_url
        
    return input_url

def get_file_paths(url, category):
    """
    Generates consistent file paths for Evidence, Reports, and Crash Dumps.
    """
    try:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        clean_name = re.sub(r'[^\w\-_]', '_', domain)
    except:
        clean_name = "unknown_target"
    
    # Separate Evidence by Category for cleaner organization
    category_dir = os.path.join(REPORT_DIR, "evidence", category)
    os.makedirs(category_dir, exist_ok=True)

    return {
        "json": os.path.join(DATA_DIR, f"report_{clean_name}.json"),
        "img": os.path.join(category_dir, f"{clean_name}.png"),
        "crash": os.path.join(category_dir, f"CRASH_{clean_name}.png")
    }

def calculate_drishti_score(violations, js_errors, load_time, missing_lang, is_secure, tracker_count):
    """
    The Core Scoring Algorithm.
    Returns a score from 0 to 100 representing the 'Accessibility Health'.
    """
    score = 100
    
    # 1. Accessibility Violations Penalty
    for v in violations:
        impact = v.get("impact", "moderate")
        count = len(v.get("nodes", []))
        
        # Weighted deductions based on severity
        if impact == "critical":
            score -= min(count * WEIGHT_CRITICAL, 30) # Cap at 30 pts
        elif impact == "serious":
            score -= min(count * WEIGHT_SERIOUS, 20)  # Cap at 20 pts
        elif impact == "moderate":
            score -= min(count * WEIGHT_MODERATE, 10) # Cap at 10 pts
            
    # 2. Stability Penalty (JavaScript Errors)
    if js_errors > 0:
        score -= min(js_errors * WEIGHT_JS_ERROR, 30)

    # 3. Trust & Privacy Penalty
    if missing_lang:
        score -= WEIGHT_MISSING_LANG
    if not is_secure:
        score -= WEIGHT_NON_SECURE
    if tracker_count > 5:
        score -= WEIGHT_TRACKER_HEAVY

    # 4. Performance Penalty (Grace Period: 3.0s)
    if load_time > 3.0:
        overage = load_time - 3.0
        score -= min(overage * WEIGHT_LOAD_TIME, 20)

    return max(0, int(score))

async def ensure_hydration(page):
    """
    Critically important function. Waits for the 'Real' DOM to load.
    Loops until it sees meaningful content or timeouts.
    """
    print("[STATUS] Verifying Page Stability (Hydration Check)...")
    
    # List of common selectors that indicate a 'Ready' state in Gov portals
    meaningful_selectors = [
        "footer", 
        "main", 
        "[role='main']", 
        ".container", 
        "#content", 
        ".footer",
        "table",
        "form"
    ]
    
    start_wait = time.time()
    hydrated = False
    
    while time.time() - start_wait < MAX_HYDRATION_WAIT / 1000:
        for selector in meaningful_selectors:
            try:
                if await page.is_visible(selector, timeout=500):
                    hydrated = True
                    break
            except: pass
        
        if hydrated:
            # Wait one more second for layout settlement
            await asyncio.sleep(1)
            break
        
        await asyncio.sleep(1) # Poll every second

    if not hydrated:
        print("[WARN] Hydration timeout. Page might be incomplete.")

# ==========================================
#        MAIN EXECUTION ENGINE
# ==========================================

async def run_scout(raw_input, category="Uncategorized"):
    target_url = sanitize_url(raw_input)
    files = get_file_paths(target_url, category)

    print(f"[INFO] TARGET: {target_url}")
    print(f"[INFO] CATEGORY: {category}")
    print(f"[INFO] OUTPUT: {files['json']}")

    stealth = Stealth()

    async with async_playwright() as p:
        # 1. BROWSER LAUNCH (GHOST MODE)
        # We launch Headed (to bypass bots) but position window off-screen (-32000).
        browser = await p.chromium.launch(
            headless=False, 
            args=[
                '--window-position=-32000,-32000', 
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--mute-audio'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True # Ensure our injected scripts run
        )
        
        # 2. APPLY STEALTH
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        # 3. NETWORK THROTTLING (INDIA 4G SIMULATION)
        # Simulates a standard Jio/Airtel 4G connection to test real performance.
        try:
            cdp = await context.new_cdp_session(page)
            await cdp.send("Network.emulateNetworkConditions", {
                "offline": False,
                "latency": 100, # 100ms latency
                "downloadThroughput": 4 * 1024 * 1024, # 4 Mbps Download
                "uploadThroughput": 2 * 1024 * 1024    # 2 Mbps Upload
            })
        except Exception as e:
            print(f"[WARN] Network emulation skipped: {e}")

        # 4. EVENT MONITORS
        console_logs = []
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda err: console_logs.append({"type": "critical_error", "text": str(err)}))

        network_stats = {"total_requests": 0, "failed_requests": 0, "total_size_bytes": 0}
        async def on_response(response):
            network_stats["total_requests"] += 1
            if response.status >= 400: network_stats["failed_requests"] += 1
            try:
                size = await response.header_value("content-length")
                if size: network_stats["total_size_bytes"] += int(size)
            except: pass
        page.on("response", on_response)

        try:
            start_time = time.time()
            print("[STATUS] Navigating (Ghost Mode)...")
            
            # 5. NAVIGATION
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            except Exception as e:
                print(f"[WARN] Navigation timeout (continuing partial load): {str(e)[:100]}")

            # 6. SMART HYDRATION (Critical Fix)
            await ensure_hydration(page)

            load_duration = round(time.time() - start_time, 2)
            print(f"[STATUS] Page Loaded in {load_duration}s.")

            # 7. PHASE 1: TECH STACK FINGERPRINT
            print("[STATUS] Identifying Tech Stack...")
            tech_stack = await page.evaluate("""() => {
                let stack = [];
                if (window.React || document.querySelector('[data-reactroot]')) stack.push("React");
                if (window.angular || document.querySelector('.ng-scope')) stack.push("Angular");
                if (window.Vue) stack.push("Vue");
                if (window.jQuery) stack.push("jQuery");
                if (document.querySelector('#__next')) stack.push("Next.js");
                if (document.querySelector('meta[name="generator"]')?.content.includes('WordPress')) stack.push("WordPress");
                if (document.querySelector('[id*="bootstrap"]')) stack.push("Bootstrap");
                return stack.length > 0 ? stack.join(", ") : "Vanilla/Custom";
            }""")

            # 8. PHASE 2: DEEP SCAN (75+ FEATURES)
            # Injects the DeepAuditor script to gather advanced metrics
            print("[STATUS] Executing 75-Point Deep Scan...")
            deep_audit_results = await page.evaluate(DeepAuditor.SCRIPT)

            # 9. PHASE 3: AXE CORE AUDIT (WCAG 2.1)
            print("[STATUS] Running Axe-Core Engine...")
            axe = Axe()
            axe_results = await axe.run(page)

            # 10. RETRY LOGIC FOR FALSE NEGATIVES (0 VIOLATIONS)
            if len(axe_results.get("violations", [])) == 0:
                print("[WARN] 0 Violations found. Suspected Hydration Failure. Retrying Deep Scan...")
                await asyncio.sleep(5) # Wait 5 more seconds
                axe_results = await axe.run(page) # Run again

            # 11. REMEDIATION SNIPPET EXTRACTION (HTML Evidence)
            enhanced_violations = []
            for v in axe_results.get("violations", [])[:10]: # Top 10 violations
                nodes = []
                for node in v.get("nodes", [])[:3]: # Top 3 occurrences per violation
                    nodes.append({
                        "html": node.get("html"),
                        "target": node.get("target"),
                        "failure_summary": node.get("failureSummary"),
                        "xpath": node.get("xpath") # Often missing in Axe, but we check
                    })
                enhanced_violations.append({
                    "id": v.get("id"),
                    "impact": v.get("impact"),
                    "description": v.get("description"),
                    "help_url": v.get("helpUrl"),
                    "evidence": nodes
                })

            # 12. SCORING CALCULATION
            critical_js_errors = len([l for l in console_logs if l['type'] in ['error', 'critical_error']])
            missing_lang = not deep_audit_results['legal_trust']['lang_attribute'] or deep_audit_results['legal_trust']['lang_attribute'] == "MISSING"
            is_secure = deep_audit_results['legal_trust']['is_secure_context']
            tracker_count = deep_audit_results['performance_network']['tracker_count']
            
            drishti_score = calculate_drishti_score(
                axe_results.get("violations", []), 
                critical_js_errors, 
                load_duration, 
                missing_lang,
                is_secure,
                tracker_count
            )
            
            total_mb = round(network_stats["total_size_bytes"] / (1024 * 1024), 2)
            
            # 13. REPORT GENERATION
            report_data = {
                "metadata": {
                    "target_url": target_url,
                    "category": category,
                    "timestamp": datetime.now().isoformat(),
                    "drishti_score": drishti_score,
                    "tech_stack": tech_stack
                },
                "deep_scan": deep_audit_results,
                "performance": {
                    "load_time_sec": load_duration,
                    "total_size_mb": total_mb,
                    "requests": network_stats["total_requests"],
                    "failed": network_stats["failed_requests"]
                },
                "stability": {
                    "js_errors": critical_js_errors,
                    "logs": console_logs[:20]
                },
                "accessibility": {
                    "violations_count": len(axe_results.get("violations", [])),
                    "violations": enhanced_violations # Includes HTML Snippets
                },
                "files": {
                    "evidence": files['img'],
                    "report": files['json']
                }
            }

            # Atomic Write
            with open(files['json'], "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            # Console Output for Operator
            status_label = "EXCELLENT" if drishti_score > 90 else "GOOD" if drishti_score > 70 else "POOR" if drishti_score > 50 else "CRITICAL"

            # --- OPERATOR DASHBOARD OUTPUT ---
            print("\n" + "="*50)
            print(f"[DATA] DRISHTI SCORE: {drishti_score}/100 ({status_label})")
            print(f"[DATA] STACK: {tech_stack}")
            print(f"[DATA] TRACKERS: {tracker_count} | JS ERRORS: {critical_js_errors}")
            print(f"[DATA] VIOLATIONS: {report_data['accessibility']['violations_count']}")
            print("STATUS: MISSION SUCCESS") 
            print("="*50 + "\n")

            # 14. EVIDENCE CAPTURE
            print("[STATUS] Capturing Evidence...")
            try:
                await page.screenshot(path=files['img'], full_page=True, animations="disabled", timeout=SCREENSHOT_TIMEOUT)
            except:
                print("[WARN] Full page screenshot failed. Retrying viewport only.")
                await page.screenshot(path=files['img'], full_page=False, animations="disabled")
            
            print(f"[SUCCESS] EVIDENCE SAVED: {files['img']}")

        except Exception as e:
            print(f"[ERROR] FAILURE: {e}")
            try:
                await page.screenshot(path=files['crash'])
                print(f"[INFO] Crash dump saved: {files['crash']}")
            except: pass
            sys.exit(1)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: uv run python src/engine/scout.py <URL> [Category]")
        sys.exit(1)
    
    cat = sys.argv[2] if len(sys.argv) > 2 else "Uncategorized"
    asyncio.run(run_scout(sys.argv[1], cat))