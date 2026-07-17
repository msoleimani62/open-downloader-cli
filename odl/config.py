"""
فارسی: خواندن/نوشتن فایل کانفیگ کاربر، و توابع کمکی برای دستورات
       «--config» (نمایش) و «--set» (تغییر تنظیمات).
English: Reading/writing the user config file, and helper functions for
         the "--config" (display) and "--set" (change settings) commands.
"""

from __future__ import annotations

import json
import os

from . import constants as c
from .logging_setup import log_warning
from .validators import validate_batch_size, validate_quality

_SETTABLE_KEYS = {
    "quality": int,
    "download_dir": str,
    "batch_size": int,
    "proxy": str,
    "proxy_pool_source": str,
    "player_client": str,
    "bypass": bool,
}

# فارسی: کلیدهای مجاز داخل یک «پروفایل دانلود» (شبیه ماکروهای فتوشاپ) —
#        همان کلیدهای تنظیمات دائمی به‌علاوه‌ی چهار سوییچ رایج سطح دستور
#        (زیرنویس انگلیسی/فارسی، فقط‌صدا، حالت پلی‌لیست) که در کانفیگ
#        دائمی معنا ندارند ولی برای یک پیش‌فرض قابل‌فراخوانی مفیدند.
# English: The keys allowed inside a "download profile" (Photoshop-macro
#          style) — the same persistent-settings keys plus four common
#          per-command switches (English/Persian subtitles, audio-only,
#          playlist mode) that don't belong in the persistent config but
#          are useful for a recallable preset.
_PROFILE_KEYS = {
    **_SETTABLE_KEYS,
    "sub_en": bool,
    "sub_fa": bool,
    "audio_only": bool,
    "playlist": bool,
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
        "profiles": {},
    }
    if c.CONFIG_FILE.exists():
        try:
            with open(c.CONFIG_FILE, encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update(user_cfg)
        except Exception as e:
            # فارسی: به‌جای بی‌صدا نادیده گرفتن، حداقل در فایل لاگ ثبت می‌شود
            #        که کانفیگ کاربر خراب بوده و به مقادیر پیش‌فرض برگشته‌ایم.
            # English: Instead of silently ignoring it, at least log that the
            #          user's config was corrupted and defaults were used.
            log_warning(f"Config file at {c.CONFIG_FILE} could not be read ({e}); using defaults.")
    return defaults


def _ensure_secure_config_dir() -> None:
    """
    فارسی: پوشه‌ی کانفیگ رو می‌سازه (اگه نبود) و دسترسیش رو محدود می‌کنه
           (700 — فقط خود کاربر). config.json رمزنگاری‌شده نیست (برخلاف
           کوکی) و می‌تونه آدرس پروکسی یا مسیرها رو نگه داره؛ روی
           دستگاه‌های اشتراکی این تنها لایه‌ی محافظتشه.
    English: Create the config directory (if missing) and restrict its
             permissions (700 — owner only). config.json isn't encrypted
             (unlike the cookie file) and can hold a proxy address or
             paths; on a shared device this is its only protection.
    """
    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(c.CONFIG_DIR, 0o700)


def save_default_config() -> None:
    """
    فارسی: اگه فایل کانفیگ وجود نداشت، یک نسخه‌ی پیش‌فرض می‌سازه.
    English: Create a default config file if one doesn't already exist.
    """
    _ensure_secure_config_dir()
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
                    "profiles": {},
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.chmod(c.CONFIG_FILE, 0o600)


def write_config(cfg: dict) -> None:
    """
    فارسی: دیکشنری تنظیمات را کامل روی فایل کانفیگ می‌نویسد.
    English: Write a full settings dict to the config file.
    """
    _ensure_secure_config_dir()
    with open(c.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.chmod(c.CONFIG_FILE, 0o600)


def _parse_key_value(arg: str, allowed_keys: dict[str, type]) -> tuple[str, object]:
    """
    فارسی: منطق مشترک پارس «کلید=مقدار» — هم برای «--set» (کلیدهای
           تنظیمات دائمی) و هم برای «--save-profile» (کلیدهای پروفایل)
           استفاده می‌شود؛ allowed_keys مشخص می‌کند کدام کلیدها و با چه
           نوعی مجازند.
    English: Shared "key=value" parsing logic — used by both "--set"
             (persistent-setting keys) and "--save-profile" (profile
             keys); allowed_keys determines which keys are valid and
             their expected type.

    Returns:
        (key, converted_value)
    """
    if "=" not in arg:
        raise ValueError(f"Invalid format '{arg}', expected key=value")

    key, raw_value = arg.split("=", 1)
    key = key.strip()
    raw_value = raw_value.strip()

    if key not in allowed_keys:
        allowed = ", ".join(sorted(allowed_keys))
        raise ValueError(f"Unknown setting '{key}'. Allowed: {allowed}")

    value_type = allowed_keys[key]

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
        except ValueError as err:
            raise ValueError(f"'{key}' expects an integer, got '{raw_value}'") from err
        if key == "batch_size":
            validate_batch_size(int_value)
        if key == "quality":
            validate_quality(int_value)
        return key, int_value

    return key, raw_value


def parse_set_argument(arg: str) -> tuple[str, object]:
    """
    فارسی: یک آرگومان به‌شکل «کلید=مقدار» (مثل quality=720) را برای
           «--set» پارس می‌کند (فقط کلیدهای تنظیمات دائمی مجازند).
    English: Parse a "key=value" argument (e.g. quality=720) for "--set"
             (only persistent-setting keys are allowed).
    """
    return _parse_key_value(arg, _SETTABLE_KEYS)


def validate_profile_settings(settings: dict) -> None:
    """
    فارسی: مقادیر یک پروفایل را پیش از ذخیره اعتبارسنجی می‌کند (کلید
           مجاز بودن، quality در لیست مجاز، batch_size حداقل ۱) — چون
           پروفایل هم مثل config.json دستی قابل‌ویرایش است و ممکن است
           یک مقدار نامعتبر بعداً کل دانلود را کرش کند.
    English: Validate a profile's values before saving (allowed key,
             quality within the allowed list, batch_size at least 1) —
             since a profile, like config.json, is hand-editable, and an
             invalid value could later crash the whole download.
    """
    for key, value in settings.items():
        if key not in _PROFILE_KEYS:
            allowed = ", ".join(sorted(_PROFILE_KEYS))
            raise ValueError(f"Unknown profile setting '{key}'. Allowed: {allowed}")
        if key == "quality":
            validate_quality(value)
        if key == "batch_size":
            validate_batch_size(value)


def load_profiles() -> dict[str, dict]:
    """
    فارسی: تمام پروفایل‌های ذخیره‌شده را برمی‌گرداند.
    English: Return all saved profiles.
    """
    return load_config().get("profiles", {})


def get_profile(name: str) -> dict | None:
    """
    فارسی: تنظیمات یک پروفایل خاص را برمی‌گرداند، یا None اگر وجود نداشت.
    English: Return a specific profile's settings, or None if it doesn't exist.
    """
    return load_profiles().get(name)


def save_profile(name: str, settings: dict) -> None:
    """
    فارسی: یک پروفایل جدید می‌سازد یا پروفایل هم‌نام موجود را بازنویسی می‌کند.
    English: Create a new profile, or overwrite an existing one with the same name.
    """
    cfg = load_config()
    profiles = cfg.get("profiles", {})
    profiles[name] = settings
    cfg["profiles"] = profiles
    write_config(cfg)


def delete_profile(name: str) -> bool:
    """
    فارسی: یک پروفایل را حذف می‌کند. اگر پروفایل وجود نداشت، False برمی‌گرداند.
    English: Delete a profile. Returns False if the profile didn't exist.
    """
    cfg = load_config()
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        return False
    del profiles[name]
    cfg["profiles"] = profiles
    write_config(cfg)
    return True
