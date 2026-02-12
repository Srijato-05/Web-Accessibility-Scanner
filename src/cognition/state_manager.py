import sqlite3
import json
import os
import logging
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("MissionLogger")

# ==========================================
#        SHARED AGENT STATE SCHEMA
# ==========================================
class AgentState(TypedDict):
    """
    The Single Source of Truth for the Squad.
    Passed securely between agents.
    """
    mission_id: str
    target_url: str
    goal: str
    
    # Navigation Context
    current_url: str
    dom_snapshot: List[Dict[str, Any]] # The Semantic Map
    screenshot_path: str
    
    # Execution History
    history_steps: List[str]   # ["Clicked #login", "Wait 2s", "Typed 'admin'"]
    
    # Diagnostics
    detected_violations: List[Dict[str, Any]]
    
    # Remediation
    proposed_fixes: List[Dict[str, str]]
    
    # Meta
    error_log: List[str]
    status: str  # "PLANNING", "NAVIGATING", "ANALYZING", "FIXING", "VERIFYING", "COMPLETED", "FAILED"

# ==========================================
#        PERSISTENCE LAYER (Thread-Safe)
# ==========================================
DB_PATH = os.path.join("reports", "audit_data.db")

class MissionLogger:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        # check_same_thread=False allows multi-agent access
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return dict-like rows
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    url TEXT,
                    goal TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    status TEXT,
                    final_score INTEGER,
                    state_blob JSON  -- Full state dump for recovery
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS mission_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    agent_role TEXT,
                    action_type TEXT,
                    details TEXT,
                    FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
                )
            ''')

    def start_mission(self, state: AgentState):
        """Initializes a mission in the DB."""
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO missions (mission_id, url, goal, start_time, status, state_blob)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    state['mission_id'], 
                    state['target_url'], 
                    state['goal'], 
                    datetime.now(), 
                    "STARTED",
                    json.dumps(state) # Snapshot initial state
                ))
            logger.info(f"Mission {state['mission_id']} initialized.")
        except Exception as e:
            logger.error(f"DB Error (Start): {e}")

    def log_action(self, mission_id: str, agent: str, action: str, details: Any):
        """Logs an atomic action for audit trails."""
        try:
            payload = json.dumps(details) if isinstance(details, (dict, list)) else str(details)
            with self.conn:
                self.conn.execute('''
                    INSERT INTO mission_actions (mission_id, agent_role, action_type, details)
                    VALUES (?, ?, ?, ?)
                ''', (mission_id, agent, action, payload))
        except Exception as e:
            logger.error(f"DB Error (Log): {e}")

    def update_state_snapshot(self, state: AgentState):
        """Updates the JSON blob for crash recovery."""
        try:
            with self.conn:
                self.conn.execute('''
                    UPDATE missions SET state_blob = ?, status = ? WHERE mission_id = ?
                ''', (json.dumps(state), state['status'], state['mission_id']))
        except Exception as e:
            logger.error(f"DB Error (Update): {e}")

    def load_mission_state(self, mission_id: str) -> Optional[AgentState]:
        """Recovers a mission from the DB."""
        try:
            cursor = self.conn.execute('SELECT state_blob FROM missions WHERE mission_id = ?', (mission_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"DB Error (Load): {e}")
        return None

    def close(self):
        self.conn.close()

# Singleton
mission_db = MissionLogger()