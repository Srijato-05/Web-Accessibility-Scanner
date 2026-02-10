import asyncio
import json
import sys
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from axe_core_python.async_playwright import Axe

# ==========================================
#        PATH PATCHING (CRITICAL FIX)
# ==========================================
# Finds 'src/utils/helpers.py' regardless of run location
current_file_path = os.path.abspath(__file__)               
engine_dir = os.path.dirname(current_file_path)             
src_dir = os.path.dirname(engine_dir)                       
utils_dir = os.path.join(src_dir, "utils")                  
project_root = os.path.dirname(src_dir)                     

# Force add paths to system
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)
sys.path.insert(0, utils_dir)

# Import the Brain
try:
    from helpers import *
except ImportError:
    try:
        from src.utils.helpers import *
    except ImportError as e:
        print(f"[FATAL] Could not find 'helpers.py'.")
        print(f"[DEBUG] Searched in: {utils_dir}")
        print(f"[DEBUG] Python Error: {e}")
        sys.exit(1)

# ==========================================
#        MAIN EXECUTION ENGINE
# ==========================================

async def resilient_axe_scan(page, axe):
    """
    Failsafe Axe Scan: Tries full page, falls back to body/main if it times out.
    """
    try:
        # Attempt 1: Full Page Scan (Most Comprehensive)
        print("[AXE] Attempting Full Page Scan...")
        return await axe.run(page)
    except Exception as e:
        print(f"[WARN] Full scan failed/timed out: {str(e)[:50]}...")
        
        try:
            # Attempt 2: Target specific containers (Lighter)
            print("[AXE] Fallback: Scanning 'body' only...")
            return await axe.run(page, context={"include": ["body"]})
        except Exception as e2:
            print(f"[WARN] Body scan failed. Trying fallback to main...")
            try:
                return await axe.run(page, context={"include": ["main", "[role='main']"]})
            except:
                print("[CRITICAL] Axe completely failed. Returning empty report.")
                return {"violations": []}

async def run_scout(raw_input, category="Uncategorized"):
    target_url = sanitize_url(raw_input)
    files = get_file_paths(target_url, category)

    print(f"[INFO] TARGET: {target_url}")
    print(f"[INFO] CATEGORY: {category}")
    print(f"[INFO] OUTPUT: {files['json']}")

    stealth = Stealth()

    async with async_playwright() as p:
        # 1. BROWSER LAUNCH
        browser = await p.chromium.launch(
            headless=False, 
            args=[
                '--window-position=-32000,-32000', 
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox', 
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--mute-audio',
                '--enable-features=NetworkService,NetworkServiceInProcess'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True, 
            locale='en-IN',
            timezone_id='Asia/Kolkata'
        )
        
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        # 2. NETWORK THROTTLING
        try:
            cdp = await context.new_cdp_session(page)
            await cdp.send("Network.emulateNetworkConditions", {
                "offline": False,
                "latency": 100, 
                "downloadThroughput": 4 * 1024 * 1024, 
                "uploadThroughput": 2 * 1024 * 1024    
            })
        except Exception as e:
            print(f"[WARN] Network emulation skipped: {e}")

        # 3. MONITORS
        console_logs = []
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda err: console_logs.append({"type": "critical_error", "text": str(err)}))

        network_stats = {"total_requests": 0, "failed_requests": 0, "total_size_bytes": 0}
        response_headers = {} 

        async def on_response(response):
            network_stats["total_requests"] += 1
            if response.status >= 400: network_stats["failed_requests"] += 1
            try:
                size = await response.header_value("content-length")
                if size: network_stats["total_size_bytes"] += int(size)
                if response.url == page.url:
                    response_headers.update(await response.all_headers())
            except: pass
        page.on("response", on_response)

        try:
            start_time = time.time()
            print("[STATUS] Navigating (Ghost Mode)...")
            
            # 4. NAVIGATION
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            except Exception as e:
                print(f"[WARN] Navigation timeout: {str(e)[:100]}")

            # 5. SMART HYDRATION & SCROLL
            await smart_scroll_and_hydrate(page)
            
            # Reset scroll for screenshot
            try:
                await page.evaluate("window.scrollTo(0, 0)")
            except: pass

            load_duration = round(time.time() - start_time, 2)
            print(f"[STATUS] Page Loaded in {load_duration}s.")

            # 6. TECH STACK
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
                if (window.L) stack.push("Leaflet Maps");
                return stack.length > 0 ? stack.join(", ") : "Vanilla/Custom";
            }""")

            # 7. DEEP SCAN (With Crash Protection)
            print("[STATUS] Executing 80-Point Deep Scan...")
            try:
                deep_audit_results = await page.evaluate(DeepAuditor.SCRIPT)
            except Exception as e:
                print(f"[FATAL] Deep Scan JS Failed: {e}")
                # Fallback to prevent crash
                deep_audit_results = {
                    "legal_trust": {"is_secure": True, "lang_attribute": "missing"},
                    "performance_vitals": {"tracker_count": 0},
                    "performance_network": {"mobile_reflow_issue": False},
                    "content_integrity": {"declared_lang": "missing", "language_mismatch": False},
                    "pii_security": {"aadhaar_detected": False, "pan_detected": False}
                }

            # 8. AXE CORE AUDIT (RESILIENT)
            print("[STATUS] Running Resilient Axe-Core Engine...")
            axe = Axe()
            axe_results = await resilient_axe_scan(page, axe)

            if len(axe_results.get("violations", [])) == 0:
                print("[WARN] 0 Violations. Retrying with deeper wait...")
                await asyncio.sleep(5) 
                axe_results = await resilient_axe_scan(page, axe)

            # 9. EVIDENCE EXTRACTION
            enhanced_violations = []
            for v in axe_results.get("violations", [])[:15]: 
                nodes = []
                for node in v.get("nodes", [])[:5]: 
                    nodes.append({
                        "html": node.get("html"),
                        "target": node.get("target"),
                        "failure_summary": node.get("failureSummary"),
                        "xpath": node.get("xpath") 
                    })
                enhanced_violations.append({
                    "id": v.get("id"),
                    "impact": v.get("impact"),
                    "description": v.get("description"),
                    "tags": v.get("tags"),
                    "evidence": nodes
                })

            # 10. SCORING (Defensive Access)
            critical_js_errors = len([l for l in console_logs if l['type'] in ['error', 'critical_error']])
            
            # Safe Access using .get() to prevent KeyError
            legal_trust = deep_audit_results.get('legal_trust', {})
            content_integrity = deep_audit_results.get('content_integrity', {})
            pii_security = deep_audit_results.get('pii_security', {})
            perf_vitals = deep_audit_results.get('performance_vitals', {})
            perf_net = deep_audit_results.get('performance_network', {})

            missing_lang = not content_integrity.get('declared_lang') or content_integrity.get('declared_lang') == "missing"
            is_secure = legal_trust.get('is_secure', False)
            tracker_count = perf_vitals.get('tracker_count', 0)
            mobile_issue = perf_net.get('mobile_reflow_issue', False)
            pii_leak = pii_security.get('aadhaar_detected', False) or pii_security.get('pan_detected', False)
            
            drishti_score = calculate_drishti_score(
                axe_results.get("violations", []), 
                critical_js_errors, 
                load_duration, 
                missing_lang,
                is_secure,
                tracker_count,
                mobile_issue,
                pii_leak
            )
            
            total_mb = round(network_stats["total_size_bytes"] / (1024 * 1024), 2)
            
            report_data = {
                "metadata": {
                    "target_url": target_url,
                    "category": category,
                    "timestamp": datetime.now().isoformat(),
                    "drishti_score": drishti_score,
                    "tech_stack": tech_stack,
                    "scan_profile": "Titanium_v10"
                },
                "deep_scan": deep_audit_results,
                "forensics": {
                    "response_headers": response_headers, 
                    "network_profile": "India 4G Simulation"
                },
                "performance": {
                    "load_time_sec": load_duration,
                    "total_size_mb": total_mb,
                    "requests": network_stats["total_requests"],
                    "failed": network_stats["failed_requests"]
                },
                "stability": {
                    "js_errors": critical_js_errors,
                    "logs": console_logs[:30]
                },
                "accessibility": {
                    "violations_count": len(axe_results.get("violations", [])),
                    "violations": enhanced_violations 
                },
                "files": {
                    "evidence": files['img'],
                    "report": files['json']
                }
            }

            with open(files['json'], "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            status_label = "EXCELLENT" if drishti_score > 90 else "GOOD" if drishti_score > 70 else "POOR" if drishti_score > 50 else "CRITICAL"

            print("\n" + "="*60)
            print(f" DRISHTI-AX SCAN RESULTS ")
            print("="*60)
            print(f"[SCORE]  {drishti_score}/100 ({status_label})")
            print(f"[STACK]  {tech_stack}")
            print("-" * 60)
            print(f"[STATS]  Load Time: {load_duration}s | Size: {total_mb}MB")
            print(f"[RISKS]  Trackers: {tracker_count} | JS Errors: {critical_js_errors}")
            print(f"[A11Y]   Violations: {report_data['accessibility']['violations_count']}")
            
            if pii_leak:
                print(f"[ALERT]  CRITICAL PRIVACY LEAK DETECTED (Aadhaar/PAN)")
            if content_integrity.get('language_mismatch'):
                print(f"[ALERT]  LANGUAGE SCRIPT MISMATCH (English Declared / Indian Script Found)")
            if mobile_issue:
                print(f"[ALERT]  MOBILE REFLOW FAILURE (Horizontal Scroll)")
            
            print("="*60 + "\n")

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