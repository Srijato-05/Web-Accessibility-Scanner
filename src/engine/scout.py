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

# --- SYSTEM CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
EVIDENCE_DIR = os.path.join(REPORT_DIR, "evidence")
DATA_DIR = os.path.join(REPORT_DIR, "data")

# Tuning Parameters
SCREENSHOT_TIMEOUT = 8000 
NAVIGATION_TIMEOUT = 90000 # Increased for slow government servers
HYDRATION_SLEEP = 12 # Increased for heavy Angular apps like IRCTC

# Ensure output directories exist
os.makedirs(EVIDENCE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def sanitize_url(input_url):
    """
    Normalizes input URLs and maps common aliases to deep links.
    """
    input_url = input_url.strip().lower()
    
    alias_map = {
        "irctc": "https://www.irctc.co.in/nget/train-search",
        "amazon": "https://www.amazon.in",
        "google": "https://www.google.com",
        "flipkart": "https://www.flipkart.com",
        "epfo": "https://www.epfindia.gov.in"
    }
    
    # Check exact alias match or sub-domain match
    for key, val in alias_map.items():
        if input_url == key or input_url == f"www.{key}.com" or input_url == f"{key}.in":
            return val

    # Standard Protocol Handling
    if not input_url.startswith("http"):
        if "." not in input_url:
            input_url = f"www.{input_url}.com"
        input_url = "https://" + input_url
        
    return input_url

def get_file_paths(url):
    """
    Generates deterministic, safe filenames based on the URL domain.
    """
    try:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        clean_name = re.sub(r'[^\w\-_]', '_', domain)
    except Exception:
        clean_name = "unknown_target"
    
    return {
        "json": os.path.join(DATA_DIR, f"report_{clean_name}.json"),
        "img": os.path.join(EVIDENCE_DIR, f"evidence_{clean_name}.png"),
        "crash": os.path.join(EVIDENCE_DIR, f"crash_{clean_name}.png")
    }

async def run_scout(raw_input):
    target_url = sanitize_url(raw_input)
    files = get_file_paths(target_url)

    print(f"[INFO] STARTING SCAN: {target_url}")
    print(f"[INFO] JSON OUTPUT: {files['json']}")

    stealth = Stealth()

    async with async_playwright() as p:
        # Launch options tuned for maximum compatibility vs anti-bot
        browser = await p.chromium.launch(
            headless=False, # Must be False for deep government scans
            args=[
                '--start-maximized', 
                '--disable-blink-features=AutomationControlled', 
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage' # Prevents crashes in low-memory docker environments
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ignore_https_errors=True # Crucial for some government sites with expired certs
        )
        
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        try:
            # --- PHASE 1: NAVIGATION ---
            print("[STATUS] Navigating to target...")
            try:
                # 'domcontentloaded' is faster; we handle hydration manually
                await page.goto(target_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
            except Exception as e:
                print(f"[WARN] Initial navigation timed out or failed: {str(e)[:100]}")
                print("[INFO] Attempting to proceed assuming partial load...")

            # --- PHASE 2: HYDRATION ---
            print(f"[STATUS] Waiting {HYDRATION_SLEEP}s for application hydration...")
            await asyncio.sleep(HYDRATION_SLEEP)

            # --- PHASE 3: AUDIT ---
            print("[STATUS] Injecting Axe-Core engine...")
            axe = Axe()
            results = await axe.run(page)

            # --- PHASE 4: INTERACTIVE MAPPING ---
            print("[STATUS] Mapping interactive DOM elements...")
            interactive_map = await page.evaluate("""() => {
                const selectors = 'button, a, input, select, textarea, [tabindex="0"], [role="button"]';
                const elements = document.querySelectorAll(selectors);
                return Array.from(elements).map(el => {
                    const rect = el.getBoundingClientRect();
                    return {
                        tag: el.tagName,
                        text: (el.innerText || el.ariaLabel || el.placeholder || "").trim().substring(0, 100),
                        x: Math.round(rect.x), y: Math.round(rect.y),
                        w: Math.round(rect.width), h: Math.round(rect.height),
                        visible: (rect.width > 0 && rect.height > 0)
                    };
                }).filter(el => el.visible);
            }""")

            # --- PHASE 5: REPORT GENERATION ---
            report_data = {
                "target_url": target_url,
                "timestamp": datetime.now().isoformat(),
                "scan_duration_sec": 0, # Placeholder, calculated by batch runner
                "metrics": {
                    "total_violations": len(results.get("violations", [])),
                    "interactive_elements": len(interactive_map),
                    "passes": len(results.get("passes", [])),
                    "incomplete": len(results.get("incomplete", []))
                },
                "files": {
                    "evidence": files['img'],
                    "report": files['json']
                },
                "violations": results.get("violations", [])
            }

            # Atomic write to ensure file integrity
            with open(files['json'], "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            # Critical output tags for Batch Runner parsing
            print(f"[SUCCESS] REPORT SAVED: {files['json']}")
            print(f"[DATA] VIOLATIONS: {report_data['metrics']['total_violations']} | ELEMENTS: {report_data['metrics']['interactive_elements']}")
            print("STATUS: MISSION SUCCESS") 

            # --- PHASE 6: EVIDENCE COLLECTION ---
            print("[STATUS] capturing visual evidence...")
            try:
                # Attempt full page first
                await page.screenshot(path=files['img'], full_page=True, animations="disabled", timeout=SCREENSHOT_TIMEOUT)
            except Exception:
                print("[WARN] Full page screenshot failed. Fallback to viewport capture.")
                try:
                    await page.screenshot(path=files['img'], full_page=False, animations="disabled")
                except Exception as e:
                     print(f"[ERROR] Evidence capture failed completely: {e}")
            
            print(f"[SUCCESS] EVIDENCE SAVED: {files['img']}")

        except Exception as e:
            print(f"[ERROR] CRITICAL FAILURE: {e}")
            # Crash Dump
            try:
                await page.screenshot(path=files['crash'])
                print(f"[INFO] Crash dump saved: {files['crash']}")
            except:
                pass
            sys.exit(1) # Return non-zero exit code to signal failure
        
        finally:
            print("[INFO] Closing browser session.")
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: uv run python src/engine/scout.py <URL>")
        sys.exit(1)
    
    asyncio.run(run_scout(sys.argv[1]))