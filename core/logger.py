"""
Structured logging, retry logic, and monitoring for the AI Agent system.

Provides:
- JSON-formatted structured logging
- Retry decorator with exponential backoff
- Error classification
- System health reporting
"""

import logging
import json
import time
import functools
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for machine parsing."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if record.exc_info and record.exc_info[1]:
            log_entry["error_type"] = type(record.exc_info[1]).__name__
            log_entry["error_msg"] = str(record.exc_info[1])
        return json.dumps(log_entry)


def get_logger(name, level=logging.INFO):
    """Create a logger with both human-readable console and JSON file output."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler — human readable
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-20s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # File handler — structured JSON
    try:
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, "agent.log"))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not create log file — falling back to console only.")

    return logger


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class ErrorClassifier:
    """Categorise exceptions into actionable types for monitoring."""

    CATEGORIES = {
        "network":    (ConnectionError, TimeoutError, OSError),
        "api":        (),  # OpenAI errors added dynamically
        "ocr":        (),
        "filesystem": (FileNotFoundError, PermissionError, IsADirectoryError),
        "validation": (ValueError, TypeError, KeyError),
    }

    @classmethod
    def classify(cls, error):
        """Return (category, is_retryable) for a given exception."""
        for category, exc_types in cls.CATEGORIES.items():
            if exc_types and isinstance(error, exc_types):
                retryable = category in ("network", "api")
                return category, retryable

        # Check by name for optional dependencies
        error_name = type(error).__name__
        if "openai" in type(error).__module__.lower() if hasattr(type(error), "__module__") else False:
            return "api", True
        if "tesseract" in error_name.lower() or "ocr" in str(error).lower():
            return "ocr", False

        return "unknown", False


# ---------------------------------------------------------------------------
# Retry decorator with exponential backoff
# ---------------------------------------------------------------------------

def retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0,
          retryable_categories=("network", "api")):
    """
    Decorator that retries a function on classified-retryable errors.

    Uses exponential backoff: delay = base_delay * (backoff_factor ** attempt).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or "retry")
            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    category, is_retryable = ErrorClassifier.classify(e)

                    if not is_retryable or attempt == max_attempts:
                        logger.error(
                            "Operation failed [%s] after %d attempt(s): %s",
                            category, attempt, e,
                            exc_info=True,
                        )
                        raise

                    delay = base_delay * (backoff_factor ** (attempt - 1))
                    logger.warning(
                        "Retryable error [%s] on attempt %d/%d — retrying in %.1fs: %s",
                        category, attempt, max_attempts, delay, e,
                    )
                    time.sleep(delay)

            raise last_error  # should not reach here, but safety net
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------

class TaskTimer:
    """Context manager that tracks elapsed time in milliseconds."""

    def __init__(self):
        self.start = None
        self.elapsed_ms = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.perf_counter() - self.start) * 1000)


# ---------------------------------------------------------------------------
# Health report
# ---------------------------------------------------------------------------

def print_system_health():
    """Print a formatted system health summary to the console."""
    from memory.memory_store import get_system_health, get_failure_patterns

    health = get_system_health()
    failures = get_failure_patterns(5)

    print("\n" + "=" * 50)
    print("  AI AGENT — SYSTEM HEALTH REPORT")
    print("=" * 50)
    print(f"  Total tasks executed:  {health['total_tasks']}")
    print(f"  Successes:             {health['successes']}")
    print(f"  Failures:              {health['failures']}")
    print(f"  Success rate:          {health['success_rate']}%")
    print(f"  Avg duration:          {health['avg_duration_ms'] or 'N/A'} ms")
    print(f"  Unresolved errors:     {health['unresolved_errors']}")

    if failures:
        print("\n  Top failure patterns:")
        for f in failures:
            print(f"    - {f['error_type']}: {f['count']}x (last: {f['last_seen'][:10]})")

    print("=" * 50 + "\n")
