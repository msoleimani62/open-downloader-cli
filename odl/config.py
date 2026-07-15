"""
فارسی: خواندن/نوشتن فایل کانفیگ کاربر، و توابع کمکی برای دستورات
       «--config» (نمایش) و «--set» (تغییر تنظیمات).
English: Reading/writing the user config file, and helper functions for
         the "--config" (display) and "--set" (change settings) commands.
"""

from __future__ import annotations

import json
from typing import Optional

from . import constants as c
from .logging_setup import log_warning

_SETTABLE_KEYS = {
    "quality": int,
    "download_dir": str,
    "batch_size": int,
    "proxy": str,
    "proxy_pool_source": str,
    "player_client": str,
    "bypass": bool,
}


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
        "proxy_pool_source": None,
        "player_client": None,
        "bypass": False,
    }
    if c.CONFIG_FILE.exists():
        try:
            with open(c.CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update(user_cfg)
        except Exception as e:
            # فارسی: به‌جای بی‌صدا نادیده گرفتن، حداقل در فایل لاگ ثبت می‌شود
            #        که کانفیگ کاربر خراب بوده و به مقادیر پیش‌فرض برگشته‌ایم.
            # English: Instead of silently ignoring it, at least log that the
            #          user's config was corrupted and defaults were used.
            log_warning(f"Config file at {c.CONFIG_FILE} could not be read ({e}); using defaults.")
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
                    "proxy_pool_source": None,
                    "player_client": None,
                    "bypass": False,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def write_config(cfg: dict) -> None:
    """
    فارسی: دیکشنری تنظیمات را کامل روی فایل کانفیگ می‌نویسد.
    English: Write a full settings dict to the config file.
    """
    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(c.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def parse_set_argument(arg: str) -> tuple[str, object]:
    """
    فارسی: یک آرگومان به‌شکل «کلید=مقدار» (مثل quality=720) را پارس کرده
           و مقدار را به نوع درست تبدیل می‌کند.
    English: Parse a "key=value" argument (e.g. quality=720) and convert
             the value to the correct type.

    Returns:
        (key, converted_value)
    """
    if "=" not in arg:
        raise ValueError(f"Invalid format '{arg}', expected key=value")

    key, raw_value = arg.split("=", 1)
    key = key.strip()
    raw_value = raw_value.strip()

    if key not in _SETTABLE_KEYS:
        allowed = ", ".join(sorted(_SETTABLE_KEYS))
        raise ValueError(f"Unknown setting '{key}'. Allowed: {allowed}")

    value_type = _SETTABLE_KEYS[key]

    if raw_value.lower() in ("none", "null", ""):
        return key, None

    if value_type is bool:
        if raw_value.lower() in ("true", "1", "yes"):
            return key, True
        if raw_value.lower() in ("false", "0", "no"):
            return key, False
        raise ValueError(f"'{key}' expects true/false, got '{raw_value}'")

    if value_type is int:
        try:
            int_value = int(raw_value)
        except ValueError:
            raise ValueError(f"'{key}' expects an integer, got '{raw_value}'")
        if key == "batch_size" and int_value < 1:
            raise ValueError(f"'batch_size' must be 1 or greater, got {int_value}")
        if key == "quality" and int_value not in c.ALLOWED_QUALITIES:
            allowed = ", ".join(map(str, c.ALLOWED_QUALITIES))
            raise ValueError(f"'quality' must be one of: {allowed}")
        return key, int_value

    return key, raw_value
