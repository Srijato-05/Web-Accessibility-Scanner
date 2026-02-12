from fastmcp import FastMCP
import subprocess
import json
import os
import glob

# Initialize the Server
mcp = FastMCP("SentryGo-Auditor")

@mcp.tool()
def audit_website(url: str) -> str:
    """
    Scans a website for accessibility violations using Playwright & Axe-Core.
    Args:
        url: The full URL to scan (e.g., 'https://www.irctc.co.in/nget/train-search')
    Returns:
        A concise summary of the violations and the location of the evidence files.
    """
    print(f"🤖 AI Command Received: Audit {url}")
    
    # 1. CLEAN UP: Remove old reports for this specific domain to avoid confusion
    domain_clean = url.split('//')[-1].split('/')[0].replace('.', '_')
    expected_file = f"report_{domain_clean}.json"
    if os.path.exists(expected_file):
        os.remove(expected_file)

    # 2. EXECUTE: Run the scout.py worker
    try:
        # We use 'uv run' to ensure it uses the correct environment
        process = subprocess.run(
            ["uv", "run", "python", "scout.py", url],
            capture_output=True,
            text=True,
            timeout=120 # 2 minutes max
        )
        
        # Log stdout for debugging
        print(process.stdout)

    except subprocess.TimeoutExpired:
        return "❌ Scout timed out after 120 seconds. The site is too slow or blocking connection."

    # 3. ANALYZE: Check if the specific report file was created
    if not os.path.exists(expected_file):
         return f"❌ Mission executed, but '{expected_file}' was not generated. Check terminal logs for crash details."

    # 4. SUMMARIZE: Read the JSON and give the AI the key facts
    with open(expected_file, "r") as f:
        data = json.load(f)
    
    violations = data.get("violations", [])
    violation_count = len(violations)
    elements_count = data.get("metrics", {}).get("interactive_elements", "N/A")
    evidence = data.get("evidence_image", "None")
    
    summary = f"✅ Audit Complete for {url}\n"
    summary += f"📊 Violations Found: {violation_count}\n"
    summary += f"📍 Interactive Elements Mapped: {elements_count}\n"
    summary += f"📸 Evidence Saved: {evidence}\n\n"
    
    if violation_count > 0:
        summary += "🚨 Top 3 Critical Issues:\n"
        for v in violations[:3]:
            # Clean up the description for better readability
            desc = v.get("description", "No description").replace("\n", " ")
            summary += f"- [{v.get('impact', 'unknown')}] {v.get('help', 'Issue')}: {desc}\n"
    else:
        summary += "🎉 Clean Scan! No violations found."

    return summary

if __name__ == "__main__":
    mcp.run()