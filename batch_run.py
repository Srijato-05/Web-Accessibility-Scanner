import json
import subprocess
import time
import os
import csv
import signal
import sys
import re
import random
import sqlite3
from datetime import datetime

# ==========================================
#        SYSTEM CONFIGURATION
# ==========================================
TARGETS_FILE = "targets.json"
DB_FILE = "reports/audit_data.db"
SUMMARY_CSV = "reports/batch_summary.csv"
# Robust path handling for cross-platform compatibility
SCOUT_SCRIPT = os.path.join("src", "engine", "scout.py") 

# Tuning
PROCESS_TIMEOUT = 200            
COOLDOWN_RANGE = (2, 5)          
MAX_RETRIES = 1                  

# ==========================================
#        DATABASE MANAGER (SQLite)
# ==========================================
class AuditDatabase:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE)
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
        self.conn.commit()

    def log_scan(self, data):
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

    def get_last_score(self, url):
        self.cursor.execute('SELECT score FROM audits WHERE url = ? ORDER BY timestamp DESC LIMIT 1', (url,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def close(self):
        self.conn.close()

# ==========================================
#        ORCHESTRATOR LOGIC
# ==========================================
current_process = None
db = None

def signal_handler(sig, frame):
    print("\n\n[SYSTEM] INTERRUPT RECEIVED. Safe shutdown initiated...")
    if current_process:
        current_process.terminate()
    if db:
        db.close()
    print("[SYSTEM] Database closed. State saved. Exiting.")
    sys.exit(0)

def load_targets():
    if not os.path.exists(TARGETS_FILE):
        print(f"[FATAL] Target file '{TARGETS_FILE}' not found.")
        print("[ACTION] Please run 'python src/tools/generate_targets.py' first!")
        sys.exit(1)
    with open(TARGETS_FILE, "r") as f:
        return json.load(f)

def get_report_path(url):
    try:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        clean_name = re.sub(r'[^\w\-_]', '_', domain)
        return os.path.join("reports", "data", f"report_{clean_name}.json")
    except:
        return ""

def log_to_csv(data, regression_alert=""):
    file_exists = os.path.exists(SUMMARY_CSV)
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    
    headers = ["Timestamp", "Sector", "URL", "Status", "Score", "Regression", "Violations", "Load Time", "PII Leak", "Mobile Fail", "Stack"]
    
    with open(SUMMARY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists: writer.writerow(headers)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("category"), data.get("url"), data.get("status"), data.get("score"),
            regression_alert, data.get("violations"), data.get("load_time"),
            data.get("pii_leak"), data.get("mobile_fail"), data.get("stack")
        ])

def run_batch():
    global current_process, db
    
    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs("reports", exist_ok=True)
    db = AuditDatabase()
    
    targets = load_targets()
    task_queue = []
    for sector, urls in targets.items():
        for url in urls:
            task_queue.append((sector, url))

    total = len(task_queue)
    print(f"\n[SYSTEM] DRISHTI-AX ORCHESTRATOR (TITANIUM EDITION)")
    print(f"[CONFIG] Using Python: {sys.executable}")
    print(f"[CONFIG] Engine: {SCOUT_SCRIPT}")
    print(f"[STATUS] Loaded {total} targets.")
    print("-" * 80)
    time.sleep(1)

    for i, (sector, url) in enumerate(task_queue):
        print(f"\n[{i + 1}/{total}] Launching Scout: {url}")
        
        start_time = time.time()
        scan_result = {
            "url": url, "category": sector, "status": "Failed", 
            "score": 0, "violations": 0, "load_time": 0, 
            "pii_leak": False, "mobile_fail": False, "stack": "Unknown"
        }
        
        prev_score = db.get_last_score(url)
        
        # Prepare Environment for Subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")

        try:
            for attempt in range(MAX_RETRIES + 1):
                if attempt > 0: print(f"       [RETRY] Attempt {attempt}/{MAX_RETRIES}...")
                
                current_process = subprocess.Popen(
                    [sys.executable, SCOUT_SCRIPT, url, sector],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env 
                )
                
                stdout, stderr = current_process.communicate(timeout=PROCESS_TIMEOUT)
                duration = round(time.time() - start_time, 2)

                # [CRITICAL FIX] Updated Success Condition logic
                # We check for returncode 0 AND look for the new output strings
                is_success = current_process.returncode == 0
                has_success_msg = "DRISHTI-AX SCAN RESULTS" in stdout or "EVIDENCE SAVED" in stdout

                if is_success and has_success_msg:
                    scan_result["status"] = "Success"
                    scan_result["load_time"] = duration
                    
                    json_path = get_report_path(url)
                    if os.path.exists(json_path):
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
                        
                        print(f"       [SUCCESS] Score: {scan_result['score']} | Time: {scan_result['load_time']}s")
                        
                        reg_msg = ""
                        if prev_score is not None:
                            diff = scan_result["score"] - prev_score
                            if diff < -10:
                                print(f"       [ALERT]   MAJOR REGRESSION detected! ({prev_score} -> {scan_result['score']})")
                                reg_msg = f"DROP ({diff})"
                        
                        db.log_scan(scan_result)
                        log_to_csv(scan_result, reg_msg)
                        break 
                    else:
                        print("       [ERROR] JSON report file not found despite success flag.")
                else:
                    if attempt == MAX_RETRIES:
                        print(f"       [FAILED] Return Code: {current_process.returncode}")
                        
                        # Debug Output
                        if stderr:
                            print(f"\n[DEBUG RAW ERROR]:\n{stderr.strip()}")
                        elif stdout and not has_success_msg:
                            print(f"\n[DEBUG RAW OUTPUT (Last 5 lines)]:\n{stdout.strip().splitlines()[-5:]}")
                        
                        scan_result["status"] = "Crash"
                        db.log_scan(scan_result)
                        log_to_csv(scan_result)

        except subprocess.TimeoutExpired:
            current_process.kill()
            print(f"       [TIMEOUT] Hard limit reached.")
            scan_result["status"] = "Timeout"
            db.log_scan(scan_result)
            log_to_csv(scan_result)

        except Exception as e:
            print(f"       [CRITICAL] Harness Error: {e}")
            
        sleep_time = random.uniform(*COOLDOWN_RANGE)
        time.sleep(sleep_time)

    print("-" * 80)
    print("[SYSTEM] BATCH RUN COMPLETE.")
    db.close()

if __name__ == "__main__":
    run_batch()