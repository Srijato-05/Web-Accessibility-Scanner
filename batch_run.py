import asyncio
import json
import sys
import os
import time
import random
import sqlite3
import signal
import re
import csv
from datetime import datetime
import warnings

# Suppress noisy Windows Proactor warnings during forced shutdown
warnings.filterwarnings("ignore", category=ResourceWarning)

# Optional Resource Guard (Prevents PC Freeze)
try:
    import psutil
    RESOURCE_GUARD_ACTIVE = True
except ImportError:
    RESOURCE_GUARD_ACTIVE = False
    print("[WARN] 'psutil' not installed. RAM protection disabled.")

# ==========================================
#        SYSTEM CONFIGURATION
# ==========================================
TARGETS_FILE = "targets.json"
DB_FILE = "reports/audit_data.db"
SUMMARY_CSV = "reports/batch_summary.csv"

# Absolute path to prevent "File Not Found" errors
SCOUT_SCRIPT = os.path.abspath(os.path.join("src", "engine", "scout.py"))

# SWARM SETTINGS
WORKER_COUNT = 5                 # Safe limit for 16GB RAM (approx 3GB usage)
RAM_THRESHOLD_PERCENT = 85.0     # Pause new scans if RAM exceeds this
PROCESS_TIMEOUT = 300            # 5 minutes max per site before killing
COOLDOWN_RANGE = (2, 5)          # Jitter between scans to avoid WAF blocks

# CHECKPOINT SETTINGS
# True  = Re-scan sites that failed/crashed previously
# False = Skip ANY site that is in the DB (even if it failed)
RETRY_FAILED_TARGETS = False     

# ==========================================
#        DATABASE MANAGER
# ==========================================
class AuditDatabase:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        # check_same_thread=False is REQUIRED for async workers
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                sector TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                score INTEGER,
                violations INTEGER,
                load_time REAL,
                status TEXT,
                pii_leak BOOLEAN,
                mobile_fail BOOLEAN,
                tech_stack TEXT
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON audits (url)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON audits (status)')
        self.conn.commit()

    def log_scan(self, data):
        """Atomic write to DB."""
        try:
            self.cursor.execute('''
                INSERT INTO audits (url, sector, score, violations, load_time, status, pii_leak, mobile_fail, tech_stack)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("url"),
                data.get("category"),
                data.get("score"),
                data.get("violations"),
                data.get("load_time"),
                data.get("status"),
                data.get("pii_leak"),
                data.get("mobile_fail"),
                data.get("stack")
            ))
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] Could not log scan: {e}")

    def get_completed_targets(self):
        """
        Smart Checkpointing:
        Returns a set of URLs that are considered 'Done' based on RETRY settings.
        """
        try:
            if RETRY_FAILED_TARGETS:
                # If retrying failures, only consider 'Success' as done.
                self.cursor.execute("SELECT DISTINCT url FROM audits WHERE status = 'Success'")
            else:
                # If not retrying, consider ANY entry as done.
                self.cursor.execute("SELECT DISTINCT url FROM audits")
            
            return {row[0] for row in self.cursor.fetchall()}
        except: return set()

    def get_last_score(self, url):
        try:
            self.cursor.execute('SELECT score FROM audits WHERE url = ? ORDER BY timestamp DESC LIMIT 1', (url,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except: return None

    def close(self):
        self.conn.close()

# ==========================================
#        UTILITIES
# ==========================================
shutdown_event = asyncio.Event()

def load_targets():
    if not os.path.exists(TARGETS_FILE):
        print(f"[FATAL] {TARGETS_FILE} not found. Run generate_targets.py first.")
        sys.exit(1)
    with open(TARGETS_FILE, "r") as f:
        return json.load(f)

def get_report_path(url):
    try:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        clean_name = re.sub(r'[^\w\-_]', '_', domain)
        return os.path.join("reports", "data", f"report_{clean_name}.json")
    except: return ""

def log_to_csv(data, regression_alert=""):
    try:
        file_exists = os.path.exists(SUMMARY_CSV)
        os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
        headers = ["Timestamp", "Sector", "URL", "Status", "Score", "Regression", "Violations", "Load Time", "PII Leak", "Mobile Fail", "Stack"]
        
        # Open in append mode with utf-8
        with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(headers)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data.get("category"), data.get("url"), data.get("status"), data.get("score"),
                regression_alert, data.get("violations"), data.get("load_time"),
                data.get("pii_leak"), data.get("mobile_fail"), data.get("stack")
            ])
    except Exception as e:
        print(f"[CSV ERROR] {e}")

async def check_resources():
    """Monitors RAM usage to prevent system freeze."""
    if not RESOURCE_GUARD_ACTIVE: return
    while True:
        try:
            if psutil.virtual_memory().percent < RAM_THRESHOLD_PERCENT: break
            # Silent wait to avoid console spam
            await asyncio.sleep(5)
        except: break

# ==========================================
#        THE WORKER AGENT
# ==========================================
async def worker_agent(worker_id, queue, db):
    """
    A persistent worker that pulls tasks from the queue until empty.
    """
    print(f"[WORKER {worker_id}] Online.")
    
    while not queue.empty() and not shutdown_event.is_set():
        try:
            task_data = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        idx, total, sector, url = task_data
        
        # 1. Resource Check
        await check_resources()
        if shutdown_event.is_set(): break
        
        print(f"[WORKER {worker_id}] Processing [{idx}/{total}]: {url}")
        
        start_time = time.time()
        scan_result = {
            "url": url, "category": sector, "status": "Failed", 
            "score": 0, "violations": 0, "load_time": 0, 
            "pii_leak": False, "mobile_fail": False, "stack": "Unknown"
        }
        
        prev_score = db.get_last_score(url)

        # Prepare Env (Preserve PYTHONPATH)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")

        # 2. Run Scout (Subprocess)
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, SCOUT_SCRIPT, url, sector,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Wait for result, but listen for global shutdown
            try:
                stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=PROCESS_TIMEOUT)
                stdout = stdout_b.decode('utf-8', errors='replace')
                stderr = stderr_b.decode('utf-8', errors='replace')
                
                is_success = process.returncode == 0
                has_success_msg = "DRISHTI-AX SCAN RESULTS" in stdout or "EVIDENCE SAVED" in stdout

                if is_success and has_success_msg:
                    scan_result["status"] = "Success"
                    scan_result["load_time"] = round(time.time() - start_time, 2)
                    
                    # Ingest Report
                    json_path = get_report_path(url)
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                report_data = json.load(f)
                            
                            meta = report_data.get("metadata", {})
                            deep = report_data.get("deep_scan", {})
                            
                            scan_result["score"] = meta.get("drishti_score", 0)
                            scan_result["violations"] = report_data["accessibility"]["violations_count"]
                            scan_result["load_time"] = report_data["performance"]["load_time_sec"]
                            scan_result["stack"] = meta.get("tech_stack", "Unknown")
                            scan_result["pii_leak"] = deep.get("pii_security", {}).get("aadhaar_detected")
                            scan_result["mobile_fail"] = deep.get("performance_network", {}).get("mobile_reflow_issue")
                            
                            # Console Feedback
                            msg = f"   ✅ DONE ({scan_result['score']}): {url}"
                            if scan_result['pii_leak']: msg += " [CRITICAL: PII LEAK]"
                            print(msg)
                            
                            reg_msg = ""
                            if prev_score is not None:
                                diff = scan_result["score"] - prev_score
                                if diff < -10: reg_msg = f"DROP ({diff})"
                            
                            db.log_scan(scan_result)
                            log_to_csv(scan_result, reg_msg)
                        except:
                            print(f"   [ERROR] Corrupt JSON for {url}")
                    else:
                        print(f"   [ERROR] Missing JSON for {url}")
                else:
                    print(f"   ❌ FAILED {url}")
                    # Debug output only on failure
                    # if stderr: print(f"      [DEBUG] {stderr.strip()[:100]}")
                    
                    scan_result["status"] = "Crash"
                    db.log_scan(scan_result)
                    log_to_csv(scan_result)

            except asyncio.TimeoutError:
                print(f"   ⏱️ TIMEOUT {url}")
                try: process.kill()
                except: pass
                scan_result["status"] = "Timeout"
                db.log_scan(scan_result)
                log_to_csv(scan_result)

        except Exception as e:
            print(f"   ⚠️ EXEC ERROR {url}: {repr(e)}")

        # Mark task done and cool down
        queue.task_done()
        await asyncio.sleep(random.uniform(*COOLDOWN_RANGE))
    
    print(f"[WORKER {worker_id}] Retiring.")

# ==========================================
#        ORCHESTRATOR
# ==========================================
async def main():
    print(f"\n[SYSTEM] DRISHTI-AX SENTINEL COMMANDER v3")
    print(f"[CONFIG] Checkpointing: {'Retrying Failures' if RETRY_FAILED_TARGETS else 'Skipping All DB Entries'}")
    
    if not os.path.exists(SCOUT_SCRIPT):
        print(f"[FATAL] Scout script not found at: {SCOUT_SCRIPT}")
        return

    db = AuditDatabase()
    completed_urls = db.get_completed_targets()
    print(f"[RESUME] Found {len(completed_urls)} checkpoints in DB.")

    targets = load_targets()
    
    # Fill the Queue
    queue = asyncio.Queue()
    queued_count = 0
    
    all_items = []
    for sector, urls in targets.items():
        for url in urls:
            all_items.append((sector, url))
    
    # Filter and enqueue
    for i, (sector, url) in enumerate(all_items):
        if url not in completed_urls:
            # Format: (Index, Total, Sector, URL)
            queue.put_nowait((i+1, len(all_items), sector, url))
            queued_count += 1
            
    print(f"[STATUS] Enqueued {queued_count} targets for scanning.")
    print(f"[CONFIG] Spawning {WORKER_COUNT} Worker Agents...")
    print("=" * 60)

    if queued_count == 0:
        print("[INFO] All targets scanned! Mission Complete.")
        return

    # Spawn Workers
    workers = []
    for i in range(WORKER_COUNT):
        w = asyncio.create_task(worker_agent(i+1, queue, db))
        workers.append(w)

    try:
        # Wait for all workers to finish
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        print("\n[SYSTEM] Workers cancelling...")

    print("=" * 60)
    print("[SYSTEM] ALL WORKERS RETIRED. BATCH RUN COMPLETE.")
    db.close()

if __name__ == "__main__":
    # [CRITICAL WINDOWS FIX]
    # Windows defaults to ProactorEventLoop which supports subprocesses.
    # We explicitly set it here to ensure stability.
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Catch Ctrl+C cleanly at top level
        print("\n\n[SYSTEM] USER INTERRUPT. Shutting down cleanly (Please Wait)...")
        shutdown_event.set()
        # Give workers a moment to see the event and stop
        time.sleep(2)
        sys.exit(0)