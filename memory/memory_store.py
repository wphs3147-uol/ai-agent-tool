"""
SQLite-backed persistent memory for the AI Agent system.

Stores task history, outcomes, errors, and context so the LLM can
query past interactions and improve future decision-making.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "agent_memory.db")


def _get_connection(db_path=None):
    """Create a connection to the SQLite database with WAL mode for reliability."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialise_db(db_path=None):
    """Create the schema if it doesn't already exist."""
    conn = _get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                user_input  TEXT    NOT NULL,
                routed_to   TEXT,
                plan        TEXT,
                outcome     TEXT    CHECK(outcome IN ('success', 'failure', 'partial', 'cancelled')),
                error_type  TEXT,
                error_msg   TEXT,
                duration_ms INTEGER,
                metadata    TEXT    DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS interaction_context (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     INTEGER NOT NULL,
                role        TEXT    NOT NULL CHECK(role IN ('system', 'user', 'assistant')),
                content     TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                FOREIGN KEY (task_id) REFERENCES task_history(id)
            );

            CREATE TABLE IF NOT EXISTS error_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                task_id     INTEGER,
                error_type  TEXT    NOT NULL,
                error_msg   TEXT    NOT NULL,
                component   TEXT,
                resolved    INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES task_history(id)
            );

            CREATE INDEX IF NOT EXISTS idx_task_outcome ON task_history(outcome);
            CREATE INDEX IF NOT EXISTS idx_task_routed  ON task_history(routed_to);
            CREATE INDEX IF NOT EXISTS idx_error_type   ON error_log(error_type);
        """)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def log_task(user_input, routed_to=None, plan=None, db_path=None):
    """Start a new task record and return its ID."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO task_history (timestamp, user_input, routed_to, plan)
               VALUES (?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), user_input, routed_to, plan),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_task_outcome(task_id, outcome, error_type=None, error_msg=None,
                        duration_ms=None, metadata=None, db_path=None):
    """Record the result of a completed task."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """UPDATE task_history
               SET outcome = ?, error_type = ?, error_msg = ?,
                   duration_ms = ?, metadata = ?
               WHERE id = ?""",
            (
                outcome,
                error_type,
                error_msg,
                duration_ms,
                json.dumps(metadata or {}),
                task_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_interaction(task_id, role, content, db_path=None):
    """Store a conversation turn linked to a task."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO interaction_context (task_id, role, content, timestamp)
               VALUES (?, ?, ?, ?)""",
            (task_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def log_error(error_type, error_msg, component=None, task_id=None, db_path=None):
    """Record an error for monitoring and post-mortem analysis."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO error_log (timestamp, task_id, error_type, error_msg, component)
               VALUES (?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), task_id, error_type, error_msg, component),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read operations — used by the LLM to learn from history
# ---------------------------------------------------------------------------

def get_recent_tasks(limit=10, db_path=None):
    """Return the most recent tasks for context injection."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, timestamp, user_input, routed_to, outcome,
                      error_type, duration_ms
               FROM task_history
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_similar_tasks(query_fragment, limit=5, db_path=None):
    """Find past tasks whose input resembles the current request."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, user_input, routed_to, outcome, error_type, error_msg
               FROM task_history
               WHERE user_input LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (f"%{query_fragment}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_failure_patterns(limit=10, db_path=None):
    """Retrieve recurring failure types so the LLM can avoid known pitfalls."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT error_type, COUNT(*) as count, MAX(timestamp) as last_seen
               FROM error_log
               WHERE resolved = 0
               GROUP BY error_type
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def build_memory_context(user_input, db_path=None):
    """
    Assemble a context string the LLM can use to make better decisions.

    Pulls recent history, similar past tasks, and known failure patterns
    into a structured summary for injection into the system prompt.
    """
    recent = get_recent_tasks(5, db_path)
    similar = get_similar_tasks(user_input, 3, db_path)
    failures = get_failure_patterns(5, db_path)

    parts = []

    if recent:
        lines = []
        for t in recent:
            status = t["outcome"] or "pending"
            lines.append(f"  - [{status}] \"{t['user_input']}\" → {t['routed_to'] or 'unrouted'}")
        parts.append("Recent tasks:\n" + "\n".join(lines))

    if similar:
        lines = []
        for t in similar:
            note = f" (error: {t['error_type']})" if t["error_type"] else ""
            lines.append(f"  - [{t['outcome']}] \"{t['user_input']}\"{note}")
        parts.append("Similar past tasks:\n" + "\n".join(lines))

    if failures:
        lines = [f"  - {f['error_type']}: {f['count']} occurrences" for f in failures]
        parts.append("Known failure patterns:\n" + "\n".join(lines))

    if not parts:
        return "No prior task history available."

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Monitoring helpers
# ---------------------------------------------------------------------------

def get_system_health(db_path=None):
    """Return a summary dict of system reliability metrics."""
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM task_history").fetchone()[0]
        successes = conn.execute(
            "SELECT COUNT(*) FROM task_history WHERE outcome = 'success'"
        ).fetchone()[0]
        failures = conn.execute(
            "SELECT COUNT(*) FROM task_history WHERE outcome = 'failure'"
        ).fetchone()[0]
        unresolved_errors = conn.execute(
            "SELECT COUNT(*) FROM error_log WHERE resolved = 0"
        ).fetchone()[0]
        avg_duration = conn.execute(
            "SELECT AVG(duration_ms) FROM task_history WHERE duration_ms IS NOT NULL"
        ).fetchone()[0]

        return {
            "total_tasks": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total * 100, 1) if total else 0,
            "unresolved_errors": unresolved_errors,
            "avg_duration_ms": round(avg_duration, 1) if avg_duration else None,
        }
    finally:
        conn.close()


# Auto-initialise the database on import
initialise_db()
