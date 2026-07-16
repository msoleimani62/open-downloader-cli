"""
فارسی: راه‌اندازی سیستم لاگ واقعی با ماژول logging پایتون — چرخش بر اساس
       حجم فایل (نه تعداد خط)، و فایل جدا برای خطاها.
English: Real logging setup using Python's logging module — size-based
         rotation (not line-count based), with a separate file for errors.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from . import constants as c

MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """
    فارسی: یک نمونه‌ی logger با دو handler می‌سازد: یکی برای همه‌ی رویدادها
           (odl.log) و یکی فقط برای خطاها (errors.log)، هر دو با چرخش بر
           اساس حجم.
    English: Build a logger with two handlers: one for all events
             (odl.log) and one for errors only (errors.log), both with
             size-based rotation.
    """
    global _logger
    if _logger is not None:
        return _logger

    c.LOG_DIR.mkdir(parents=True, exist_ok=True)
    # فارسی: لاگ‌ها می‌تونن URL، آدرس پروکسی، یا مسیرهای فایل رو نگه دارن؛
    #        روی دستگاه‌های اشتراکی این محدودیت تنها لایه‌ی محافظتشونه.
    # English: Logs can contain URLs, proxy addresses, or file paths; on a
    #          shared device this restriction is their only protection.
    os.chmod(c.LOG_DIR, 0o700)

    logger = logging.getLogger("odl")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

        general_handler = RotatingFileHandler(
            c.LOG_DIR / "odl.log", maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        general_handler.setLevel(logging.DEBUG)
        general_handler.setFormatter(formatter)
        logger.addHandler(general_handler)

        error_handler = RotatingFileHandler(
            c.LOG_DIR / "errors.log", maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

    _logger = logger
    return logger


def log_download_error(url: str, message: str) -> None:
    """
    فارسی: یک خطای دانلود را با سطح ERROR ثبت می‌کند.
    English: Log a download error at ERROR level.
    """
    get_logger().error("%s -> %s", url, message)


def log_info(message: str) -> None:
    """
    فارسی: یک رویداد عادی را با سطح INFO ثبت می‌کند.
    English: Log a normal event at INFO level.
    """
    get_logger().info(message)


def log_warning(message: str) -> None:
    """
    فارسی: یک هشدار (مثلاً استفاده از fallback) را با سطح WARNING ثبت می‌کند.
    English: Log a warning (e.g. a client fallback) at WARNING level.
    """
    get_logger().warning(message)


def log_debug_traceback(traceback_text: str) -> None:
    """
    فارسی: کل traceback را با سطح DEBUG در odl.log ثبت می‌کند.
    English: Log the full traceback at DEBUG level into odl.log.
    """
    get_logger().debug(traceback_text)
