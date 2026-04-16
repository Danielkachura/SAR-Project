import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from typing import Dict

WORKDIR = Path("/home/airunit/Desktop/airunit")


class ScanManager:
    def __init__(
        self,
        on_output: Optional[Callable[[str, int], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
        idle_seconds: float = 5.0,
    ):
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._idle_thread: Optional[threading.Thread] = None
        self._on_output = on_output
        self._on_exit = on_exit

        self._line_count = 0
        self._last_output_time: Optional[float] = None
        self._idle_seconds = idle_seconds
        self._idle_signaled = False

    # --- Public API ---
    def start(self) -> bool:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return False  # already running

            # Force unbuffered stdout/stderr from the sniffer
            cmd = ["sudo", "env", "PYTHONUNBUFFERED=1", "python3", "-u", "wifi_sniffer_logger.py"]
            self._proc = subprocess.Popen(
                cmd,
                cwd=WORKDIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._line_count = 0
            self._last_output_time = time.time()
            self._idle_signaled = False

            self._reader_thread = threading.Thread(target=self._reader, daemon=True)
            self._reader_thread.start()

            self._idle_thread = threading.Thread(target=self._idle_watchdog, daemon=True)
            self._idle_thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._proc or self._proc.poll() is not None:
                return False
            try:
                self._proc.send_signal(signal.SIGINT)  # mimic Ctrl+C
            except Exception:
                pass
            return True

    def status(self) -> str:
        with self._lock:
            if self._proc is None:
                return "idle"
            code = self._proc.poll()
            if code is None:
                return f"running({self._line_count})"
            return f"exited({code})"

    def line_count(self) -> int:
        with self._lock:
            return self._line_count

    # --- Internal ---
    def _reader(self):
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            with self._lock:
                self._line_count += 1
                self._last_output_time = time.time()
                self._idle_signaled = False
                count = self._line_count
            if self._on_output:
                self._on_output(line, count)

        code = self._proc.wait()
        if self._on_exit:
            self._on_exit(code)

    def _idle_watchdog(self):
        while True:
            time.sleep(1.0)
            with self._lock:
                proc_running = self._proc is not None and self._proc.poll() is None
                last = self._last_output_time
                idle_signaled = self._idle_signaled
            if not proc_running:
                break
            if last is None:
                continue
            gap = time.time() - last
            if gap >= self._idle_seconds and not idle_signaled:
                self._idle_signaled = True
                if self._on_output:
                    self._on_output(
                        f"[monitor] No feedback for {int(gap)}s (possible connection loss)",
                        self.line_count(),
                    )
