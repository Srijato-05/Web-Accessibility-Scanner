import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_pilot(url, max_tabs=100):
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Set to False to watch it work!
        context = await browser.new_context()
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        print(f"🕵️ Pilot is entering the site: {url}")
        await page.goto(url, wait_until="networkidle")

        navigation_log = []
        seen_elements = [] # To detect loops/traps

        for i in range(max_tabs):
            # 1. Tab to the next element
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.1) # Small delay to allow the site to react

            # 2. Get the current focused element info
            focused = await page.evaluate("""() => {
                const el = document.activeElement;
                const rect = el.getBoundingClientRect();
                return {
                    tag: el.tagName,
                    text: el.innerText || el.ariaLabel || "Unlabeled",
                    html: el.outerHTML.substring(0, 100), // For identification
                    x: Math.round(rect.x),
                    y: Math.round(rect.y)
                };
            }""")

            # 3. Logic: Trap Detection
            # If the same HTML shows up too many times, we are in a loop
            if focused['html'] in seen_elements[-3:]: 
                print(f"🚨 ALERT: Potential Keyboard Trap detected at element: {focused['text']}")
                navigation_log.append({"type": "TRAP", "data": focused})
                break

            seen_elements.append(focused['html'])
            navigation_log.append(focused)
            print(f"Step {i+1}: Focused on {focused['tag']} - '{focused['text']}'")

            # Break if we've reached the end of the body or a known footer
            if focused['tag'] == "BODY": break

        # Save the Journey
        with open("navigation_journey.json", "w", encoding="utf-8") as f:
            json.dump(navigation_log, f, indent=2)

        print(f"🏁 Pilot Journey Finished. {len(navigation_log)} steps recorded.")
        await browser.close()

if __name__ == "__main__":
    target = "https://www.google.com"
    asyncio.run(run_pilot(target))