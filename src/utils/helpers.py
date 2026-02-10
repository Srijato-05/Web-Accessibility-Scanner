import os
import re
import time
import asyncio
import json

# ==========================================
#        SYSTEM CONFIGURATION
# ==========================================
# Dynamically determine project root relative to this file
# src/utils/helpers.py -> src/utils -> src -> ROOT
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
SCREENSHOT_TIMEOUT = 20000       # 20s for complex rendering (Canvas/WebGL)
NAVIGATION_TIMEOUT = 120000      # 2 minutes max for slow government servers
MAX_ADAPTIVE_WAIT = 45000        # Max time we wait if the page keeps loading content
SCROLL_STEP_DELAY = 0.5          # Delay between scroll steps
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
WEIGHT_MOBILE_FAIL = 15          # Deduction for horizontal scroll issues
WEIGHT_PRIVACY_LEAK = 30         # Deduction for exposing PII (Aadhaar/PAN)

# ==========================================
#        THE DEEP AUDITOR ENGINE
# ==========================================
class DeepAuditor:
    """
    This class contains the proprietary JavaScript payload that is injected
    into the browser. It performs 80+ forensic checks covering:
    Visual, Cognitive, Legal, Structural, Network, Relational, and Integrity layers.
    It includes Shadow DOM piercing and Indian-context PII detection.
    """
    
    # [CRITICAL] Using Raw String (r"") to prevent Python escape sequence errors
    SCRIPT = r"""
    () => {
        // --- SECTION 1: INTERNAL UTILITIES ---
        
        // Recursively finds all elements, even those hidden inside Web Components (Shadow DOM)
        // This is CRITICAL for modern government apps that use Angular/Polymer.
        const getAllElements = (root = document) => {
            const nodes = Array.from(root.querySelectorAll('*'));
            const shadowNodes = nodes
                .filter(n => n.shadowRoot)
                .reduce((acc, n) => acc.concat(getAllElements(n.shadowRoot)), []);
            return nodes.concat(shadowNodes);
        };

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
                if (!element || element.nodeType === 9) break; // Break at Document Root
            }
            return `/${sPath.join('/')}`;
        };

        // Checks if an element is actually visible to a human user
        const isVisible = (el) => {
            if (!el.getBoundingClientRect) return false;
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 && 
                   style.visibility !== 'hidden' &&
                   style.display !== 'none' &&
                   style.opacity !== '0';
        };

        // Estimates reading level using Flesch-Kincaid logic
        const fleschKincaidEstimate = (text) => {
            const words = text.split(/\s+/).length;
            const sentences = text.split(/[.!?]+/).length || 1;
            return (0.39 * (words / sentences)) + 11.8; 
        };

        // --- SECTION 2: DATA HARVESTING ---
        
        const allEls = getAllElements(); // Capture Shadow DOM elements too
        const interactiveSelector = 'button, a, input, select, textarea, [role="button"], [tabindex="0"]';
        const interactive = allEls.filter(el => el.matches && el.matches(interactiveSelector) && isVisible(el));
        const images = allEls.filter(el => el.tagName === 'IMG');
        const bodyText = document.body.innerText || "";
        
        // --- PILLAR 1: SENSORY & COGNITIVE ---
        const motionElements = document.querySelectorAll('video, marquee, .parallax, [data-aos], canvas');
        const flashingElements = document.querySelectorAll('blink, .flash, .blink, [class*="animate"]');
        
        // --- PILLAR 2: NAVIGATION & STRUCTURE ---
        const landmarks = document.querySelectorAll('main, nav, header, footer, aside, [role="main"], [role="navigation"]');
        
        // Focus Order Logic: Check if tabbing jumps wildly around the page
        const focusOrder = interactive.map(el => {
            const r = el.getBoundingClientRect();
            return { tag: el.tagName, y: Math.round(r.y), x: Math.round(r.x) };
        });
        const erraticFocus = focusOrder.some((curr, i) => {
            if (i === 0) return false;
            const prev = focusOrder[i-1];
            // If current element is 200px *above* the previous one, it's a "Jump Back"
            return curr.y < prev.y - 200; 
        });

        // --- PILLAR 3: CONTENT INTEGRITY (ALT QUALITY & LANGUAGE) ---
        // 3a. Alt Text Forensics
        const junkAltRegex = /^(image|photo|picture|graphic|icon|logo|img_|dsc_|screen|untitled|placeholder)$/i;
        const fileExtRegex = /\.(jpg|png|svg|gif|webp)$/i;
        
        const badAltImages = images.filter(img => {
            const alt = (img.alt || "").trim();
            if (!alt) return false; // Empty alt is handled by Axe (checking presentation role)
            // Flag if alt matches junk words OR contains file extensions
            return junkAltRegex.test(alt) || fileExtRegex.test(alt);
        });

        // 3b. Language Script Integrity (Indian Context)
        // Checks if page declares 'en' but contains significant Devanagari/Bengali/Tamil/Telugu etc.
        const indianScriptRegex = /[\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]/;
        const declaredLang = (document.documentElement.lang || "missing").toLowerCase();
        const hasIndianContent = indianScriptRegex.test(bodyText.substring(0, 5000)); // Sample first 5k chars
        const languageMismatch = declaredLang.startsWith("en") && hasIndianContent;

        // 3c. PII Leak Detection (Indian Context) - CRITICAL PRIVACY CHECK
        const aadhaarRegex = /[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}/; // Format: XXXX XXXX XXXX
        const panRegex = /[A-Z]{5}[0-9]{4}[A-Z]{1}/; // Format: ABCDE1234F
        const mobileRegex = /(?:(?:\+|0{0,2})91(\s*[\-]\s*)?|[0]?)?[789]\d{9}/;
        
        const piiLeak = {
            aadhaar_detected: aadhaarRegex.test(bodyText),
            pan_detected: panRegex.test(bodyText),
            mobile_exposed: mobileRegex.test(bodyText.substring(0, 1000)) // Check header/footer
        };

        // --- PILLAR 4: PERFORMANCE & MOBILE ---
        // Layout Shifts: Detect elements with absolute/fixed positioning that might float
        const potentialLayoutShifts = allEls.filter(el => {
            const style = window.getComputedStyle(el);
            return (style.position === 'absolute' || style.position === 'fixed') && !el.closest('nav, header, footer');
        }).length;

        // Third-Party Trackers: Analyze script sources
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        const trackers = scripts.filter(s => /google|facebook|analytics|ad|pixel|tag|manager/i.test(s.src));
        
        // Heavy Images: Find unoptimized assets
        const heavyImages = images.filter(img => {
            return img.naturalWidth > 1600 || img.src.endsWith('.png');
        });

        // Mobile Reflow Risk: Check if content overflows horizontally
        const horizontalOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth;

        // --- PILLAR 5: LEGAL & TRUST ---
        const privacyLinks = Array.from(document.querySelectorAll('a')).filter(a => /privacy|terms|policy|disclaimer/i.test(a.innerText));
        const contactLinks = Array.from(document.querySelectorAll('a')).filter(a => /contact|help|support|reach/i.test(a.innerText));
        const hasCaptcha = !!document.querySelector('iframe[src*="captcha"], .g-recaptcha, [id*="captcha"]');
        
        // Evasion Detection: Look for common soft-block messages
        const botChallengeDetected = /cloudflare|hcaptcha|verify you are human|security check/i.test(document.title);

        // --- PILLAR 6: INTERACTIVE (RELATIONAL MAPPING) ---
        // This creates a "Map" for the Phase 3 AI Agent to understand the page structure
        const elementTree = interactive.slice(0, 60).map(el => ({
            tag: el.tagName,
            text: (el.innerText || el.ariaLabel || el.placeholder || "").trim().substring(0, 50).replace(/\n/g, ' '),
            parent_tag: el.parentElement ? el.parentElement.tagName : "BODY",
            xpath: getElementXpath(el),
            is_visible: true, // Filtered above
            attributes: {
                role: el.getAttribute('role'),
                type: el.getAttribute('type'),
                aria_label: el.getAttribute('aria-label'),
                aria_expanded: el.getAttribute('aria-expanded')
            }
        }));

        // --- SECTION 3: COMPILATION & RETURN ---
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
            content_integrity: {
                bad_alt_count: badAltImages.length,
                language_mismatch_detected: languageMismatch,
                declared_lang: declaredLang,
                has_indian_script: hasIndianContent,
                pii_leak_detected: piiLeak
            },
            performance_network: {
                total_scripts: scripts.length,
                tracker_count: trackers.length,
                heavy_image_count: heavyImages.length,
                potential_layout_shifts: potentialLayoutShifts,
                dom_depth: Math.max(...Array.from(allEls).map(e => e.getElementsByTagName('*').length)),
                mobile_reflow_issue: horizontalOverflow,
                shadow_roots_found: allEls.filter(e => e.shadowRoot).length
            },
            legal_trust: {
                has_privacy_policy: privacyLinks.length > 0,
                has_contact_info: contactLinks.length > 0,
                has_captcha_barrier: hasCaptcha,
                is_secure_context: window.isSecureContext,
                bot_challenge_detected: botChallengeDetected,
                meta_viewport: document.querySelector('meta[name="viewport"]')?.content || "MISSING"
            },
            interactive_relational: {
                small_touch_targets: interactive.filter(el => {
                    const r = el.getBoundingClientRect();
                    return r.width < 44 || r.height < 44;
                }).length,
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
#        CORE HELPER FUNCTIONS
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
        "uidai": "https://uidai.gov.in",
        "sbi": "https://www.onlinesbi.sbi"
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

def calculate_drishti_score(violations, js_errors, load_time, missing_lang, is_secure, tracker_count, mobile_issue, pii_leak):
    """
    The Core Scoring Algorithm.
    Returns a score from 0 to 100 representing the 'Accessibility Health'.
    Now includes Privacy Leaks (Aadhaar/PAN) as a major penalty factor.
    """
    score = 100
    
    # 1. Accessibility Violations Penalty (Cap: 40 pts)
    for v in violations:
        impact = v.get("impact", "moderate")
        count = len(v.get("nodes", []))
        
        if impact == "critical":
            score -= min(count * WEIGHT_CRITICAL, 35) 
        elif impact == "serious":
            score -= min(count * WEIGHT_SERIOUS, 25)  
        elif impact == "moderate":
            score -= min(count * WEIGHT_MODERATE, 15) 
            
    # 2. Stability Penalty (Cap: 30 pts)
    if js_errors > 0:
        score -= min(js_errors * WEIGHT_JS_ERROR, 30)

    # 3. Trust & Privacy Penalty
    if missing_lang:
        score -= WEIGHT_MISSING_LANG
    if not is_secure:
        score -= WEIGHT_NON_SECURE
    if tracker_count > 5:
        score -= WEIGHT_TRACKER_HEAVY
    if mobile_issue:
        score -= WEIGHT_MOBILE_FAIL
    
    # 4. Critical Privacy Failure (Aadhaar/PAN leak)
    if pii_leak:
        score -= WEIGHT_PRIVACY_LEAK

    # 5. Performance Penalty (Grace Period: 3.0s)
    if load_time > 3.0:
        overage = load_time - 3.0
        score -= min(overage * WEIGHT_LOAD_TIME, 20)

    return max(0, int(score))

async def smart_scroll_and_hydrate(page):
    """
    ADVANCED HYDRATION (Redirect-Proof):
    Scrolls down incrementally to trigger lazy-loads.
    Specifically designed to handle "Rug Pull" redirects by government sites.
    If the page navigates while scrolling, it aborts the scroll gracefully and continues audit.
    """
    print("[STATUS] Initiating Smart Scroll & Hydration...")
    
    try:
        # 1. Get initial height (Safe)
        try:
            last_height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            return # Page died immediately
        
        # 2. Incremental Scroll (Human-like) with Redirect Protection
        for i in range(1, 5): # Scroll in 4 chunks
            try:
                await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/4})")
                await asyncio.sleep(SCROLL_STEP_DELAY)
            except Exception as e:
                # [CRITICAL FIX] Detect Navigation/Context Destruction
                error_msg = str(e).lower()
                if "execution context" in error_msg or "target closed" in error_msg or "navigating" in error_msg:
                    print("[INFO] Page navigated/redirected during scroll. Stopping hydration to prevent crash.")
                    return # Stop scrolling, proceed to audit the NEW page
                else:
                    raise e # Re-raise if it's a different error
        
        # 3. Wait for network to settle
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except: pass 
        
        # 4. Check for infinite scroll expansion (Safe)
        try:
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height > last_height:
                print("[INFO] Infinite scroll detected. Extending wait...")
                await asyncio.sleep(2) 
        except: pass

        # 5. Stability Check (Are key elements present?)
        meaningful_selectors = ["footer", "main", "[role='main']", ".container", "#content", "table", "form"]
        hydrated = False
        for selector in meaningful_selectors:
            try:
                if await page.is_visible(selector, timeout=500):
                    hydrated = True
                    break
            except: pass
                
        if not hydrated:
            print("[WARN] Page might be incomplete (No main container found).")
        else:
            print("[INFO] Page appears stable.")

    except Exception as e:
        print(f"[WARN] Hydration partial failure: {str(e)[:100]}")