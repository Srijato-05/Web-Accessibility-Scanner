import json
import subprocess
import time
import os
import csv
import signal
import sys
import re
from datetime import datetime

# ==========================================
#        SYSTEM CONFIGURATION
# ==========================================
TARGETS_FILE = "targets.json"
STATE_FILE = "batch_state.json"
SUMMARY_CSV = "reports/batch_summary.csv"
STATS_JSON = "reports/batch_stats.json"
SCOUT_SCRIPT = "src/engine/scout.py"

# Tuning: Must be higher than Scout's internal timeout (120s)
PROCESS_TIMEOUT = 150 

# ==========================================
#        GLOBAL STATE TRACKER
# ==========================================
current_process = None

def load_targets():
    """Loads the target list and categories from JSON."""
    if not os.path.exists(TARGETS_FILE):
        print(f"[ERROR] Target file '{TARGETS_FILE}' not found. Cannot proceed.")
        sys.exit(1)
    with open(TARGETS_FILE, "r") as f:
        return json.load(f)

def load_state():
    """Loads previous run state to enable resume functionality."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[WARN] State file corrupted. Starting fresh.")
    return {"completed": [], "failed": [], "pending": []}

def save_state(state):
    """Saves current progress to disk for crash recovery."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def update_dashboard_stats(category, score, violations, trackers, js_errors):
    """
    Updates the Sector Analytics JSON. 
    This feeds the "Wall of Shame" and Sector Comparison charts.
    """
    if os.path.exists(STATS_JSON):
        try:
            with open(STATS_JSON, "r") as f:
                stats = json.load(f)
        except:
            stats = {"total_scanned": 0, "categories": {}}
    else:
        stats = {"total_scanned": 0, "categories": {}}

    stats["total_scanned"] += 1
    
    if category not in stats["categories"]:
        stats["categories"][category] = {
            "count": 0, 
            "total_score": 0, 
            "avg_score": 0,
            "total_violations": 0,
            "avg_violations": 0,
            "risk_profile": "Unknown"
        }
    
    cat = stats["categories"][category]
    cat["count"] += 1
    cat["total_score"] += score
    cat["total_violations"] += violations
    
    # Recalculate Averages
    cat["avg_score"] = round(cat["total_score"] / cat["count"], 1)
    cat["avg_violations"] = round(cat["total_violations"] / cat["count"], 1)

    # Risk Profiling
    if cat["avg_score"] > 80: cat["risk_profile"] = "Low"
    elif cat["avg_score"] > 50: cat["risk_profile"] = "Moderate"
    else: cat["risk_profile"] = "Critical"

    with open(STATS_JSON, "w") as f:
        json.dump(stats, f, indent=2)

def log_to_csv(data):
    """Logs detailed results to CSV for Excel analysis."""
    file_exists = os.path.exists(SUMMARY_CSV)
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    
    headers = [
        "Timestamp", "Category", "URL", "Status", "Drishti Score", 
        "Violations", "Tech Stack", "Trackers", "JS Errors", "Duration (s)"
    ]
    
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("category", "Unknown"),
            data.get("url", "Unknown"),
            data.get("status", "Failed"),
            data.get("score", 0),
            data.get("violations", 0),
            data.get("stack", "Unknown"),
            data.get("trackers", 0),
            data.get("js_errors", 0),
            data.get("duration", 0)
        ])

def signal_handler(sig, frame):
    """Gracefully handles interruptions (Ctrl+C)."""
    print("\n\n[SYSTEM] INTERRUPT SIGNAL RECEIVED.")
    print("[SYSTEM] Terminating active background process...")
    if current_process:
        current_process.terminate()
    print("[SYSTEM] State saved. Exiting safely.")
    sys.exit(0)

def run_scout_process(url, category):
    """Spawns the Scout Engine as a subprocess."""
    global current_process
    process = subprocess.Popen(
        ["uv", "run", "python", SCOUT_SCRIPT, url, category],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8', 
        errors='replace'
    )
    return process

def parse_scout_output(stdout):
    """
    Parses the raw text output from the Scout Engine to extract metrics.
    """
    data = {
        "score": 0,
        "stack": "Unknown",
        "trackers": 0,
        "js_errors": 0,
        "violations": 0
    }
    
    for line in stdout.split("\n"):
        clean_line = line.strip()
        
        # Regex extraction for robust parsing
        if "[DATA] DRISHTI SCORE:" in clean_line:
            match = re.search(r"SCORE:\s*(\d+)", clean_line)
            if match: data["score"] = int(match.group(1))
            
        if "[DATA] STACK:" in clean_line:
            data["stack"] = clean_line.split("STACK:")[1].strip()
            
        if "[DATA] TRACKERS:" in clean_line:
            # Format: [DATA] TRACKERS: 5 | JS ERRORS: 2
            parts = clean_line.split("|")
            t_match = re.search(r"TRACKERS:\s*(\d+)", parts[0])
            j_match = re.search(r"ERRORS:\s*(\d+)", parts[1])
            if t_match: data["trackers"] = int(t_match.group(1))
            if j_match: data["js_errors"] = int(j_match.group(1))

        # Fallback for Violations (usually parsed from JSON in Scout, but we scrape log here)
        # Note: Scout v6 logs this explicitly.
        if "VIOLATIONS:" in clean_line:
             v_match = re.search(r"VIOLATIONS:\s*(\d+)", clean_line)
             if v_match: data["violations"] = int(v_match.group(1))

    return data

def run_batch():
    global current_process
    
    # Register Ctrl+C handler
    signal.signal(signal.SIGINT, signal_handler)
    
    targets = load_targets()
    state = load_state()

    # Flatten Target List
    all_tasks = []
    for category, urls in targets.items():
        for url in urls:
            all_tasks.append((category, url))

    # Resume Logic
    remaining_tasks = [t for t in all_tasks if t[1] not in state["completed"]]
    
    total = len(all_tasks)
    done = len(state["completed"])
    remaining = len(remaining_tasks)

    print(f"\n[SYSTEM] DRISHTI-AX ENTERPRISE ORCHESTRATOR")
    print(f"[CONFIG] Engine: {SCOUT_SCRIPT}")
    print(f"[STATUS] Total Targets: {total} | Completed: {done} | Pending: {remaining}")
    
    if remaining == 0:
        print("[INFO] All targets processed. Delete 'batch_state.json' to restart.")
        return

    print("[INFO] Starting Ghost Mode Batch Run...")
    print("-" * 80)
    time.sleep(2)

    for i, (category, url) in enumerate(remaining_tasks):
        print(f"\n[{done + i + 1}/{total}] Processing: {url}")
        print(f"       Category: {category}")
        
        start_time = time.time()
        status = "Failed"
        parsed_data = {}
        duration = 0
        
        # Retry Loop (Max 1 Retry)
        max_retries = 1
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print("       [RETRY] Initial attempt failed. Retrying...")

            try:
                current_process = run_scout_process(url, category)
                stdout, stderr = current_process.communicate(timeout=PROCESS_TIMEOUT)
                duration = round(time.time() - start_time, 2)

                # Check for explicit Success Flag
                if current_process.returncode == 0 and "STATUS: MISSION SUCCESS" in stdout:
                    status = "Success"
                    parsed_data = parse_scout_output(stdout)
                    
                    print(f"       [SUCCESS] Score: {parsed_data['score']} | Stack: {parsed_data['stack']}")
                    print(f"                 Time: {duration}s | Violations: {parsed_data.get('violations', 'N/A')}")
                    
                    # Update Persistence
                    state["completed"].append(url)
                    save_state(state)
                    
                    # Log Data
                    log_data = {
                        "category": category,
                        "url": url,
                        "status": status,
                        "duration": duration,
                        **parsed_data
                    }
                    log_to_csv(log_data)
                    update_dashboard_stats(
                        category, 
                        parsed_data['score'], 
                        parsed_data.get('violations', 0),
                        parsed_data['trackers'],
                        parsed_data['js_errors']
                    )
                    break # Exit retry loop

                else:
                    print(f"       [FAILED] Return Code: {current_process.returncode}")
                    # Print last few lines of error for context
                    err_lines = stderr.strip().split('\n')[-2:]
                    for line in err_lines:
                        if line: print(f"       [ERROR LOG] {line}")
                    
                    if attempt == max_retries:
                        # Final Failure
                        log_to_csv({
                            "category": category, "url": url, "status": "Crash", 
                            "duration": duration, "score": 0, "violations": 0, 
                            "stack": "Unknown", "trackers": 0, "js_errors": 0
                        })
                        state["failed"].append(url)
                        state["completed"].append(url) # Mark done to prevent infinite loop
                        save_state(state)

            except subprocess.TimeoutExpired:
                current_process.kill()
                print(f"       [TIMEOUT] Process killed after {PROCESS_TIMEOUT}s")
                if attempt == max_retries:
                    log_to_csv({
                        "category": category, "url": url, "status": "Timeout", 
                        "duration": PROCESS_TIMEOUT, "score": 0, "violations": 0, 
                        "stack": "Unknown", "trackers": 0, "js_errors": 0
                    })
                    state["failed"].append(url)
                    state["completed"].append(url)
                    save_state(state)

            except Exception as e:
                print(f"       [CRITICAL] System Error: {e}")
                break
            
            # Brief cooldown between retries
            time.sleep(2)

    print("-" * 80)
    print("[SYSTEM] BATCH RUN COMPLETE.")
    print(f"[INFO] Summary saved to: {SUMMARY_CSV}")
    print(f"[INFO] Dashboard stats saved to: {STATS_JSON}")

if __name__ == "__main__":
    run_batch()