"""
فارسی: خواندن/نوشتن فایل کانفیگ کاربر و چرخش فایل لاگ.
English: Reading/writing the user config file and rotating the log file.
"""

from __future__ import annotations

import json

from . import constants as c


def load_config() -> dict:
    """
    فارسی: تنظیمات کاربر رو از فایل کانفیگ می‌خونه و با مقادیر پیش‌فرض ترکیب می‌کنه.
    English: Load user settings from the config file, merged with sane defaults.
    """
    defaults = {
        "cookies": str(c.COOKIES_DEFAULT),
        "quality": c.DEFAULT_QUALITY,
        "download_dir": str(c.DOWNLOAD_DIR_DEFAULT),
        "batch_size": c.BATCH_SIZE,
        "proxy": None,
        "player_client": None,
        "bypass": False,
    }
    if c.CONFIG_FILE.exists():
        try:
            with open(c.CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update(user_cfg)
        except Exception:
            pass
    return defaults


def save_default_config() -> None:
    """
    فارسی: اگه فایل کانفیگ وجود نداشت، یک نسخه‌ی پیش‌فرض می‌سازه.
    English: Create a default config file if one doesn't already exist.
    """
    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not c.CONFIG_FILE.exists():
        with open(c.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "cookies": str(c.COOKIES_DEFAULT),
                    "quality": c.DEFAULT_QUALITY,
                    "download_dir": str(c.DOWNLOAD_DIR_DEFAULT),
                    "batch_size": c.BATCH_SIZE,
                    "proxy": None,
                    "player_client": None,
                    "bypass": False,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def rotate_log() -> None:
    """
    فارسی: فایل لاگ را برای جلوگیری از رشد بی‌رویه، به حداکثر MAX_LOG_LINES خط محدود می‌کند.
    English: Trim the log file to at most MAX_LOG_LINES lines to prevent unbounded growth.
    """
    if not c.LOG_FILE.exists():
        return
    try:
        lines = c.LOG_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > c.MAX_LOG_LINES:
            with open(c.LOG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines[-c.MAX_LOG_LINES:]) + "\n")
    except Exception:
        pass


def log_error(url: str, message: str) -> None:
    """
    فارسی: خطای دانلود یک لینک رو با زمان‌مهر به فایل لاگ اضافه می‌کنه و لاگ رو می‌چرخاند.
    English: Append a timestamped download error for a URL to the log file and rotate it.
    """
    import time

    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(c.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {url} -> {message}\n")
    rotate_log()
