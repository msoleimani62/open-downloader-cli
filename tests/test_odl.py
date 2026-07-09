"""
فارسی: تست‌های واحد برای بخش‌های حیاتی odl.py — رمزنگاری کوکی، دسته‌بندی
       خطا، ساخت extractor_args، و توابع کمکی. این تست‌ها به شبکه یا یک
       کوکی/حساب واقعی نیاز ندارند و کاملاً آفلاین اجرا می‌شوند.
English: Unit tests for the critical parts of odl.py — cookie encryption,
         error classification, extractor_args construction, and helper
         functions. These tests need no network access or a real
         cookie/account and run fully offline.
"""

import base64
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import odl  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """
    فارسی: قبل از هر تست، مسیرهای فایل کوکی/کانفیگ را به یک پوشه‌ی موقت
           هدایت می‌کند تا هیچ تستی به فایل‌های واقعی کاربر دست نزند.
    English: Before each test, redirect cookie/config file paths to a
             temporary directory so no test ever touches the real user's files.
    """
    monkeypatch.setattr(odl, "CONFIG_DIR", tmp_path / ".config" / "opendl")
    monkeypatch.setattr(odl, "CONFIG_FILE", tmp_path / ".config" / "opendl" / "config.json")
    monkeypatch.setattr(odl, "COOKIES_DEFAULT", tmp_path / "cookies.txt")
    monkeypatch.setattr(odl, "ENCRYPTED_COOKIES_FILE", tmp_path / ".config" / "opendl" / "cookies.enc")
    monkeypatch.setattr(odl, "LOG_FILE", tmp_path / ".config" / "opendl" / "opendl.log")
    yield


class TestCookieEncryption:
    def test_derive_key_is_deterministic_for_same_password_and_salt(self):
        salt = os.urandom(16)
        key1 = odl.derive_key("my-password", salt)
        key2 = odl.derive_key("my-password", salt)
        assert key1 == key2

    def test_derive_key_differs_for_different_passwords(self):
        salt = os.urandom(16)
        key1 = odl.derive_key("password-one", salt)
        key2 = odl.derive_key("password-two", salt)
        assert key1 != key2

    def test_full_encrypt_decrypt_roundtrip_with_correct_password(self, tmp_path, monkeypatch):
        odl.COOKIES_DEFAULT.write_text(
            "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc123\n"
        )
        passwords = iter(["correct-horse-battery-staple", "correct-horse-battery-staple"])
        monkeypatch.setattr(odl.getpass, "getpass", lambda prompt="": next(passwords))

        cookie_path, cleanup = odl.secure_cookies_setup(auto=False)

        assert odl.ENCRYPTED_COOKIES_FILE.exists()
        assert not odl.COOKIES_DEFAULT.exists()

        oct_perm = oct(odl.ENCRYPTED_COOKIES_FILE.stat().st_mode)[-3:]
        assert oct_perm == "600"

        monkeypatch.setattr(odl.getpass, "getpass", lambda prompt="": "correct-horse-battery-staple")
        cfg = {"cookies": str(odl.COOKIES_DEFAULT)}
        decrypted_path, cleanup2 = odl.resolve_cookies_path(cfg)

        assert decrypted_path is not None
        content = Path(decrypted_path).read_text()
        assert "abc123" in content
        cleanup2()
        assert not Path(decrypted_path).exists()

    def test_wrong_password_is_rejected(self, monkeypatch):
        odl.COOKIES_DEFAULT.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc\n")
        passwords = iter(["right-password", "right-password"])
        monkeypatch.setattr(odl.getpass, "getpass", lambda prompt="": next(passwords))
        odl.secure_cookies_setup(auto=False)

        wrong_attempts = iter(["wrong-1", "wrong-2", "wrong-3"])
        monkeypatch.setattr(odl.getpass, "getpass", lambda prompt="": next(wrong_attempts))
        monkeypatch.setattr(odl.Confirm, "ask", staticmethod(lambda *a, **k: False))

        cfg = {"cookies": str(odl.COOKIES_DEFAULT)}
        with pytest.raises(SystemExit):
            odl.resolve_cookies_path(cfg)

    def test_auto_mode_reuses_password_without_asking_twice(self, monkeypatch):
        odl.COOKIES_DEFAULT.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc\n")
        prompts = []

        def fake_getpass(prompt=""):
            prompts.append(prompt)
            return "pw1"

        monkeypatch.setattr(odl.getpass, "getpass", fake_getpass)
        cookie_path, cleanup = odl.secure_cookies_setup(auto=True)

        assert len(prompts) == 2
        assert cookie_path is not None
        cleanup()


class TestClassifyError:
    @pytest.mark.parametrize(
        "message,expected_category",
        [
            ("The uploader has not made this video available in your country", odl.ErrorCategory.REGION_LOCKED),
            ("This is a private video", odl.ErrorCategory.PRIVATE_VIDEO),
            ("Video unavailable", odl.ErrorCategory.DELETED_VIDEO),
            ("Join this channel to get access to members-only content", odl.ErrorCategory.MEMBERS_ONLY),
            ("Sign in to confirm you're not a bot", odl.ErrorCategory.BOT_DETECTED),
            ("Please sign in to continue", odl.ErrorCategory.LOGIN_REQUIRED),
            ("SOCKS5 proxy connection failed", odl.ErrorCategory.PROXY_ERROR),
            ("cookie file is invalid or expired", odl.ErrorCategory.COOKIE_INVALID),
            ("Temporary failure in name resolution", odl.ErrorCategory.NETWORK_ERROR),
            ("some completely unrelated error text", odl.ErrorCategory.UNKNOWN),
        ],
    )
    def test_classify_error_categories(self, message, expected_category):
        assert odl.classify_error(message) == expected_category

    def test_bot_detection_is_in_retryable_categories(self):
        assert odl.ErrorCategory.BOT_DETECTED in odl.CLIENT_FALLBACK_RETRYABLE_CATEGORIES

    def test_region_locked_is_not_retryable(self):
        assert odl.ErrorCategory.REGION_LOCKED not in odl.CLIENT_FALLBACK_RETRYABLE_CATEGORIES


class TestBuildExtractorArgs:
    def test_default_skips_authcheck(self):
        args = odl.build_extractor_args({}, bypass=False)
        assert "authcheck" in args["youtubetab"]["skip"]

    def test_bypass_adds_webpage_skip_and_player_skip(self):
        args = odl.build_extractor_args({}, bypass=True)
        assert "webpage" in args["youtubetab"]["skip"]
        assert args["youtube"]["player_skip"] == ["webpage", "configs"]

    def test_player_client_single(self):
        args = odl.build_extractor_args({"player_client": "android"}, bypass=False)
        assert args["youtube"]["player_client"] == ["android"]

    def test_player_client_multiple_comma_separated(self):
        args = odl.build_extractor_args({"player_client": "android, web , mweb"}, bypass=False)
        assert args["youtube"]["player_client"] == ["android", "web", "mweb"]

    def test_bypass_and_player_client_combined(self):
        args = odl.build_extractor_args({"player_client": "android"}, bypass=True)
        assert args["youtube"]["player_skip"] == ["webpage", "configs"]
        assert args["youtube"]["player_client"] == ["android"]


class TestHelpers:
    @pytest.mark.parametrize(
        "quality,expected",
        [(480, "bestvideo[height<=480]+bestaudio/best[height<=480]"),
         (1080, "bestvideo[height<=1080]+bestaudio/best[height<=1080]")],
    )
    def test_build_format(self, quality, expected):
        assert odl.build_format(quality) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://youtu.be/abc123", True),
            ("https://www.youtube.com/watch?v=abc123", True),
            ("https://example.com/video", False),
            ("not a url at all", False),
        ],
    )
    def test_is_youtube_url(self, url, expected):
        assert odl.is_youtube_url(url) == expected

    def test_human_size_formats_correctly(self):
        assert odl.human_size(None) == "unknown"
        assert odl.human_size(0) == "unknown"
        assert "KB" in odl.human_size(2048)
        assert "MB" in odl.human_size(5 * 1024 * 1024)

    def test_resolve_video_url_from_id(self):
        entry = {"id": "abc123"}
        assert odl.resolve_video_url(entry) == "https://www.youtube.com/watch?v=abc123"

    def test_resolve_video_url_from_full_url(self):
        entry = {"url": "https://youtu.be/xyz"}
        assert odl.resolve_video_url(entry) == "https://youtu.be/xyz"

    def test_resolve_video_url_returns_none_when_empty(self):
        assert odl.resolve_video_url({}) is None

    def test_write_temp_cookie_file_permissions_and_cleanup(self):
        path, cleanup = odl._write_temp_cookie_file(b"test-data")
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"test-data"
        oct_perm = oct(Path(path).stat().st_mode)[-3:]
        assert oct_perm == "600"
        cleanup()
        assert not Path(path).exists()


class TestEnvironmentDetection:
    def test_desktop_linux_true_without_android_markers(self, monkeypatch):
        monkeypatch.setattr(odl, "_ANDROID_MARKER_PATHS", [Path("/nonexistent-marker-path")])
        for var in odl._ANDROID_MARKER_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(odl.sys, "platform", "linux")
        assert odl.is_desktop_linux() is True

    def test_desktop_linux_false_with_termux_env_var(self, monkeypatch):
        monkeypatch.setattr(odl, "_ANDROID_MARKER_PATHS", [Path("/nonexistent-marker-path")])
        monkeypatch.setenv("TERMUX_VERSION", "0.118")
        monkeypatch.setattr(odl.sys, "platform", "linux")
        assert odl.is_desktop_linux() is False
