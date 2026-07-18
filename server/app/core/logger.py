import os, json, time, threading
from datetime import datetime
from typing import Optional

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

class OperationLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_file = None
            cls._instance._current_start = None
        return cls._instance

    def _get_file(self):
        now = time.time()
        # Rotate every 6 hours
        if self._current_start is None or (now - self._current_start) >= 6 * 3600:
            self._current_start = now
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            self._current_file = os.path.join(LOG_DIR, f"operations_{ts}.log")
        return self._current_file

    def log(
        self,
        operator: str,
        action: str,
        target: str,
        success: bool,
        detail: str = "",
        method: str = "",
        path: str = "",
        client_ip: str = "",
    ):
        with self._lock:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "operator": operator,
                "action": action,
                "target": target,
                "success": success,
                "detail": detail,
                "method": method,
                "path": path,
                "client_ip": client_ip,
            }
            filepath = self._get_file()
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

logger = OperationLogger()
print(f"Logger initialized, dir: {LOG_DIR}")
