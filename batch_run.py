import json
import subprocess
import time
import os
import csv
import signal
import sys
from datetime import datetime

# --- CONFIGURATION ---
TARGETS_FILE = "targets.json"
STATE_FILE = "batch_state.json"
SUMMARY_CSV = "reports/batch_summary.csv"
STATS_JSON = "reports/batch_stats.json"
SCOUT_SCRIPT = "src/engine/scout.py"

# --- GLOBAL STATE ---
current_process = None

def load_targets():
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
    return {"completed": [], "failed": []}

def save_state(state):
    """Saves current progress to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def update_dashboard_stats(category, url, status, violations):
    """Updates a JSON file used by the frontend dashboard."""
    if os.path.exists(STATS_JSON):
        try:
            with open(STATS_JSON, "r") as f:
                stats = json.load(f)
        except:
            stats = {"total_scanned": 0, "total_violations": 0, "categories": {}}
    else:
        stats = {"total_scanned": 0, "total_violations": 0, "categories": {}}

    stats["total_scanned"] += 1
    
    if isinstance(violations, int):
        stats["total_violations"] += violations

    if category not in stats["categories"]:
        stats["categories"][category] = {"count": 0, "violations": 0}
    
    stats["categories"][category]["count"] += 1
    if isinstance(violations, int):
        stats["categories"][category]["violations"] += violations

    with open(STATS_JSON, "w") as f:
        json.dump(stats, f, indent=2)

def log_to_csv(category, url, status, violations, elements, duration):
    """Logs detailed results to CSV for Excel analysis."""
    file_exists = os.path.exists(SUMMARY_CSV)
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Category", "URL", "Status", "Violations", "Interactive Elements", "Duration (s)"])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            category, url, status, violations, elements, duration
        ])

def signal_handler(sig, frame):
    """Gracefully handles interruptions (Ctrl+C)."""
    print("\n\n[SYSTEM] INTERRUPT SIGNAL RECEIVED.")
    print("[SYSTEM] Terminating active subprocess...")
    if current_process:
        current_process.terminate()
    print("[SYSTEM] State saved. Exiting safely.")
    sys.exit(0)

def run_batch():
    global current_process
    
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    targets = load_targets()
    state = load_state()

    # Flatten the target list
    all_tasks = []
    for category, urls in targets.items():
        for url in urls:
            all_tasks.append((category, url))

    # Filter out URLs that are already in the 'completed' list
    remaining_tasks = [t for t in all_tasks if t[1] not in state["completed"]]
    
    total = len(all_tasks)
    done = len(state["completed"])
    remaining = len(remaining_tasks)

    print(f"\n[SYSTEM] SENTRY-GO ENTERPRISE BATCH ENGINE")
    print(f"[STATUS] Total Targets: {total} | Completed: {done} | Pending: {remaining}")
    
    if remaining == 0:
        print("[INFO] All targets have been processed. Delete 'batch_state.json' to restart.")
        return

    print("[INFO] Safe-Resume enabled. Press Ctrl+C at any time to pause.")
    print("-" * 70)
    time.sleep(2)

    for i, (category, url) in enumerate(remaining_tasks):
        print(f"\n[{done + i + 1}/{total}] Processing: {url} ({category})")
        
        start_time = time.time()
        status = "Failed"
        violations_count = 0
        elements_count = 0

        try:
            # Execute the Scout Engine as a subprocess
            current_process = subprocess.Popen(
                ["uv", "run", "python", SCOUT_SCRIPT, url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = current_process.communicate(timeout=110) # 110s timeout to allow for nav timeouts

            duration = round(time.time() - start_time, 2)

            # Analyze the output from the scout
            if current_process.returncode == 0 and "STATUS: MISSION SUCCESS" in stdout:
                status = "Success"
                
                # Parse metrics from stdout
                for line in stdout.split("\n"):
                    if "[DATA]" in line:
                        parts = line.split("|")
                        try:
                            violations_count = int(parts[0].split(":")[1].strip())
                            elements_count = int(parts[1].split(":")[1].strip())
                        except ValueError:
                            violations_count = 0
                            elements_count = 0
                
                print(f"   [SUCCESS] Time: {duration}s | Violations: {violations_count} | Elements: {elements_count}")
                
                # Update persistent state
                state["completed"].append(url)
                save_state(state)
                
                # Log data
                log_to_csv(category, url, status, violations_count, elements_count, duration)
                update_dashboard_stats(category, url, status, violations_count)

            else:
                print(f"   [FAILED] Time: {duration}s")
                # Log specific error details from stderr
                error_lines = stderr.strip().split('\n')
                if error_lines:
                    print(f"   [ERROR LOG] {error_lines[-1]}")
                
                state["failed"].append(url)
                # We still mark it as completed in terms of 'attempts' to prevent infinite loops on broken sites
                # Remove this line if you want to retry failed sites indefinitely
                state["completed"].append(url) 
                save_state(state)
                
                log_to_csv(category, url, "Crash", 0, 0, duration)

        except subprocess.TimeoutExpired:
            current_process.kill()
            print(f"   [TIMEOUT] Process killed after {time.time() - start_time:.1f}s")
            log_to_csv(category, url, "Timeout", 0, 0, 110)
            state["failed"].append(url)
            state["completed"].append(url)
            save_state(state)
        
        except Exception as e:
            print(f"   [CRITICAL] System Error: {e}")

        # Cooldown period to prevent rate limiting and allow memory cleanup
        time.sleep(3)

    print("-" * 70)
    print("[SYSTEM] BATCH RUN COMPLETE.")

if __name__ == "__main__":
    run_batch()