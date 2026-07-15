# 📥 Open Downloader CLI

<div align="center">

**یک دانلودر یوتیوب ساده، امن و رزیوم‌پذیر برای خط فرمان**
**A simple, secure, resumable YouTube downloader for the command line**

بر پایه‌ی / Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) · دستور اجرا / Command: `odl`

[![Tests](https://github.com/msoleimani62/open-downloader-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/msoleimani62/open-downloader-cli/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/open-downloader-cli)](https://pypi.org/project/open-downloader-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**فارسی | [English ⬇](#-english)**

</div>

---

## ⚡ شروع سریع

```bash
pip install open-downloader-cli
odl "لینک ویدیوی یوتیوب"
```

همین. بار اول اگه `cookies.txt` نداشته باشی راهنمای export نشونت می‌ده؛ اگه داشته باشی خودش با رمز اصلی رمزنگاریش می‌کنه و شروع به دانلود می‌کنه.

برای آخرین کد (که ممکنه از نسخه‌ی PyPI جدیدتر باشه):
```bash
pip install git+https://github.com/msoleimani62/open-downloader-cli.git
```

---

## 📚 فهرست مطالب

- [شروع سریع](#-شروع-سریع)
- [ویژگی‌ها](#-ویژگیها)
- [پیش‌نیازها](#-پیشنیازها)
- [نصب](#-نصب)
- [دریافت کوکی — راهنمای گام‌به‌گام](#-دریافت-کوکی--راهنمای-گامبهگام)
- [استفاده](#-استفاده)
- [پیدا کردن خودکار پروکسی](#-پیدا-کردن-خودکار-پروکسی-برای-کسایی-که-پروکسی-بلد-نیستن)
- [همه‌ی گزینه‌های خط فرمان](#-همهی-گزینههای-خط-فرمان)
- [عیب‌یابی](#-عیبیابی)
- [حذف کامل](#️-حذف-کامل)
- [نقشه‌ی راه](#-نقشهی-راه)
- [لایسنس](#-لایسنس)

---

## ✨ ویژگی‌ها

| قابلیت | توضیح |
|---|---|
| 🎬 دانلود تکی / پلی‌لیست | با نوار پیشرفت زنده و رنگی، دانلود موازی برای پلی‌لیست |
| ⏸️ رزیوم خودکار | دانلود ناتمام (قطعی نت، خاموشی گوشی) خودکار از همون‌جا ادامه پیدا می‌کنه |
| 🍪 دریافت خودکار کوکی | متناسب با محیط اجرا — دسکتاپ، اندروید روت‌شده، یا اندروید معمولی |
| 🔐 رمزنگاری کوکی | AES (از طریق Fernet) + رمز اصلی که هیچ‌جا ذخیره نمی‌شه |
| 🌐 پروکسی/Tor | پشتیبانی کامل از SOCKS5/HTTP |
| 🧭 استخر پروکسی خودکار | تست/کش/رتست خودکار از روی لیست پروکسی خودت — برای کسایی که پروکسی بلد نیستن |
| 🔁 Fallback هوشمند | تعویض خودکار کلاینت پخش یوتیوب هنگام تشخیص بات |
| 🏷️ دسته‌بندی خطا | Region Locked، Private، Bot Detection و... در خلاصه‌ی نهایی |
| 🩺 `odl --doctor` | تشخیص کامل سلامت نصب در یک نگاه |
| ⬆️ `odl --update` | آپدیت و بررسی نسخه‌ی yt-dlp |

---

## 📋 پیش‌نیازها

- Python 3.9 یا بالاتر
- کتابخانه‌های `yt-dlp` · `rich` · `cryptography`
- `ffmpeg` (برای merge صدا/تصویر و تبدیل زیرنویس)

---

## 📦 نصب

```bash
# نصب کتابخانه‌های مورد نیاز
pip install yt-dlp rich cryptography --break-system-packages

# کپی کردن اسکریپت اصلی
mkdir -p ~/.local/bin
cp odl.py ~/.local/bin/odl
chmod +x ~/.local/bin/odl
```

اگه `~/.local/bin` توی PATH نیست:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

بررسی سلامت نصب:

```bash
odl --doctor
```

---

## 🍪 دریافت کوکی — راهنمای گام‌به‌گام

> اکثر دانلودها (مخصوصاً پلی‌لیست‌ها) به کوکی نیاز دارن تا یوتیوب درخواست رو بات تشخیص نده.

### 🖥️ روی لینوکس دسکتاپ
**کاری لازم نیست.** فقط یک‌بار با فایرفاکس یا کروم وارد youtube.com شو؛ اولین اجرای `odl` خودش کوکی رو مستقیم از مرورگرت می‌خونه و رمزنگاری می‌کنه.

### 🤖 روی اندروید با روت واقعی
**کاری لازم نیست.** فقط با فایرفاکس اندروید وارد youtube.com شو؛ `odl` مستقیم از دیتابیس فایرفاکس می‌خونه.

### 📱 روی اندروید بدون روت (دستی)

| مرحله | کار |
|---|---|
| ۱ | فایرفاکس رو باز کن و با یک اکانت گوگل (ترجیحاً فرعی) وارد youtube.com شو |
| ۲ | چند ویدیو ببین تا رفتار حساب طبیعی به‌نظر برسه |
| ۳ | افزونه‌ی **cookies.txt** رو از addons.mozilla.org نصب کن |
| ۴ | توی تب یوتیوب، آیکون افزونه رو بزن و کوکی رو export کن (فایلی مثل `cookies.txt` توی Download ذخیره می‌شه) |
| ۵ | همین! دفعه‌ی بعد `odl` رو با هر لینکی بزنی، خودش فایل رو پیدا می‌کنه، رمز اصلی می‌پرسه، رمزنگاری می‌کنه و دانلود رو ادامه می‌ده |

### 🔑 اگر رمز اصلی رو فراموش کردی

```bash
odl --reset-cookies
```

فایل رمزنگاری‌شده حذف می‌شه؛ فقط یک کوکی جدید export کن و دوباره اجرا کن.

---

## 🚀 استفاده

```bash
odl "لینک ویدیو"                          # دانلود تکی، کیفیت پیش‌فرض 480p
odl -q 1080 "لینک"                         # انتخاب کیفیت
odl -a "لینک"                              # فقط صدا (mp3)
odl -s -fs "لینک"                          # زیرنویس انگلیسی + فارسی
odl -p -q 720 "لینک پلی‌لیست"              # دانلود کل پلی‌لیست
```

---

## 🌐 پیدا کردن خودکار پروکسی (برای کسایی که پروکسی بلد نیستن)

اگه پروکسی سرت نمی‌شه یا نمی‌دونی کدوم پروکسی هنوز زنده‌ست، لازم نیست دستی امتحان کنی. یک فایل متنی (یا لینک یک فایل متنی) با یک پروکسی در هر خط بده، بقیه‌ش خودکاره:

```bash
# proxies.txt — هر خط یک پروکسی؛ خط خالی و خط # نادیده گرفته می‌شه
# http://1.2.3.4:8080
# socks5://5.6.7.8:1080

odl --proxy-pool ~/proxies.txt "لینک ویدیو"
```

odl خودش یکی‌یکی پروکسی‌ها رو با یک تست واقعی (نه فقط پینگ) امتحان می‌کنه، اولین پروکسی سالم رو ذخیره می‌کنه، و دفعه‌ی بعد قبل از هر دانلود اول همون رو دوباره تست می‌کنه؛ اگه هنوز زنده بود، دیگه سراغ بقیه‌ی لیست نمی‌ره. اگه مرده بود، خودش دوباره از اول لیست می‌گرده.

```bash
# فقط تست کن ببین کدوم پروکسی‌ها الان زنده‌ن، بدون دانلود
odl --test-proxies --proxy-pool ~/proxies.txt

# اگه نمی‌خوای هر بار --proxy-pool رو تایپ کنی، یک‌بار پیش‌فرضش کن
odl --set proxy_pool_source=~/proxies.txt
odl "لینک ویدیو"   # از این به بعد خودکار از همین لیست استفاده می‌کنه

# مجبورش کن نادیده بگیره پروکسی کش‌شده رو و کل لیست رو دوباره اسکن کنه
odl --proxy-pool-refresh "لینک ویدیو"
```

⚠️ **نکته‌ی امنیتی مهم:** پروکسی‌های رایگان عمومی از منابع نامعتبر می‌تونن ترافیک شبکه‌ت رو ببینن یا حتی دستکاری کنن. odl فقط از منبعی استفاده می‌کنه که خودت بهش دادی — هیچ‌جا خودش دنبال پروکسی روی اینترنت نمی‌گرده. فقط از منبعی استفاده کن که بهش اعتماد داری.

---

## ⚙️ همه‌ی گزینه‌های خط فرمان

| گزینه | توضیح |
|---|---|
| `-p, --playlist` | حالت پلی‌لیست |
| `-q, --quality` | کیفیت: 144/240/360/480/720/1080/1440/2160 |
| `-s, --sub-en` | زیرنویس انگلیسی |
| `-fs, --sub-fa` | زیرنویس فارسی (در صورت وجود) |
| `-a, --audio-only` | فقط صدا (mp3) |
| `-o, --output` | مسیر ذخیره‌سازی سفارشی |
| `-b, --batch` | تعداد دانلود هم‌زمان در پلی‌لیست |
| `-x, --proxy` | آدرس پروکسی، مثلاً `socks5h://127.0.0.1:9050` |
| `--proxy-pool` | فایل/لینک لیست پروکسی؛ تست و کش و چرخش خودکار |
| `--proxy-pool-refresh` | نادیده گرفتن کش و اسکن کامل دوباره‌ی لیست پروکسی |
| `--test-proxies` | فقط تست کن کدوم پروکسی‌ها زنده‌ن، بدون دانلود |
| `--player-client` | اجبار کلاینت پخش خاص (مثلاً `android`) |
| `--bypass` | استخراج سبک‌تر/سریع‌تر |
| `--secure-cookies` | رمزنگاری دستی کوکی فعلی |
| `--reset-cookies` | حذف کوکی رمزنگاری‌شده (فراموشی رمز) |
| `--import-cookies` | وادار کردن به import مجدد کوکی |
| `--cookie-status` | نمایش وضعیت فعلی کوکی |
| `--no-estimate` | رد شدن از تخمین حجم (پلی‌لیست بزرگ) |
| `--debug` | اطلاعات کامل دیباگ + traceback |
| `--doctor` | بررسی سلامت نصب |
| `--check-update` | بررسی آپدیت yt-dlp بدون نصب |
| `--update` | آپدیت yt-dlp |
| `--version` | نمایش نسخه |

---

## 🔧 عیب‌یابی

| مشکل | راه‌حل |
|---|---|
| `Sign in to confirm you're not a bot` | کوکی معتبر نیست/منقضی شده → `odl --import-cookies` |
| خطای Region/جغرافیایی | از `-x` یا `--proxy-pool` با یه پروکسی/Tor در کشور مجاز استفاده کن |
| رمز اصلی یادت رفته | `odl --reset-cookies` و export مجدد |
| نمی‌دونی کدوم پروکسی زنده‌ست | `odl --test-proxies --proxy-pool ~/proxies.txt` |
| تشخیص محیط (`odl --doctor`) اشتباهه | `ODL_FORCE_ENVIRONMENT=kali_nethunter odl --doctor` (مقادیر مجاز: `android_termux`، `kali_nethunter`، `desktop_linux`، `wsl`، `other`) |
| نمی‌دونی مشکل از کجاست | `odl --doctor` و `odl --debug "لینک"` |

---

## 🗑️ حذف کامل

```bash
rm -f ~/.local/bin/odl
rm -rf ~/.config/opendl
rm -f ~/cookies.txt
```

---

## 🧭 نقشه‌ی راه

آپدیت خودکار در پس‌زمینه · پروفایل‌های چندگانه‌ی کوکی · تاریخچه‌ی دانلود · حالت تعاملی · محدودیت سرعت · زمان‌بندی دانلود · حذف موارد تکراری · اعلان بعد از اتمام · خروجی JSON · تست‌های خودکار (pytest)

---

## 📄 لایسنس

MIT — فایل [LICENSE](LICENSE) رو ببین.

<br>

---

<a name="-english"></a>
# 🇬🇧 English

<div align="center">

**A simple, secure, resumable YouTube downloader for the command line**

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) · Command: `odl`

</div>

---

## ⚡ Quick Start

```bash
pip install open-downloader-cli
odl "YouTube video URL"
```

That's it. On first run, if you don't have a `cookies.txt`, it shows you the export guide; if you do, it encrypts it with a master password and starts downloading.

For the latest code (may be ahead of the PyPI release):
```bash
pip install git+https://github.com/msoleimani62/open-downloader-cli.git
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎬 Single / playlist downloads | Live colored progress bars, concurrent playlist downloads |
| ⏸️ Automatic resume | Interrupted downloads (network drops, phone reboots) continue automatically |
| 🍪 Automatic cookie retrieval | Adapts to the environment — desktop, rooted Android, or plain Android |
| 🔐 Cookie encryption | AES (via Fernet) + a master password that is never stored anywhere |
| 🌐 Proxy/Tor support | Full SOCKS5/HTTP support |
| 🧭 Automatic proxy pool | Auto test/cache/retest from your own proxy list — for people who don't know proxies |
| 🔁 Smart fallback | Automatic YouTube playback-client switching on bot detection |
| 🏷️ Error categorization | Region Locked, Private, Bot Detection, etc. in the final summary |
| 🩺 `odl --doctor` | Full installation health check at a glance |
| ⬆️ `odl --update` | Update and check the yt-dlp version |

---

## 📋 Requirements

- Python 3.9+
- `yt-dlp` · `rich` · `cryptography`
- `ffmpeg` (for merging audio/video and converting subtitles)

---

## 📦 Installation

```bash
pip install yt-dlp rich cryptography --break-system-packages

mkdir -p ~/.local/bin
cp odl.py ~/.local/bin/odl
chmod +x ~/.local/bin/odl
```

If `~/.local/bin` isn't in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Check installation health:

```bash
odl --doctor
```

---

## 🍪 Getting Cookies — Step by Step

> Most downloads (especially playlists) need cookies so YouTube doesn't flag the request as a bot.

### 🖥️ Desktop Linux
**Nothing to do.** Just sign in to youtube.com once with Firefox or Chrome; the first `odl` run reads cookies directly from your browser and encrypts them.

### 🤖 Rooted Android
**Nothing to do.** Just sign in to youtube.com with Firefox for Android; `odl` reads directly from the Firefox database.

### 📱 Non-rooted Android (manual)

| Step | Action |
|---|---|
| 1 | Open Firefox and sign in to youtube.com with a Google account (a secondary one is recommended) |
| 2 | Watch a couple of videos so the account looks naturally active |
| 3 | Install the **cookies.txt** add-on from addons.mozilla.org |
| 4 | On the YouTube tab, tap the add-on icon and export the cookies (saved as `cookies.txt` in Downloads) |
| 5 | Done! Next `odl` run finds the file, asks for a master password, encrypts it, and continues your download |

### 🔑 If you forget the master password

```bash
odl --reset-cookies
```

The encrypted file is deleted; export a fresh cookie file and run `odl` again.

---

## 🚀 Usage

```bash
odl "video URL"                 # single download, default 480p
odl -q 1080 "URL"               # choose quality
odl -a "URL"                    # audio only (mp3)
odl -s -fs "URL"                # English + Persian subtitles
odl -p -q 720 "playlist URL"    # download an entire playlist
```

---

## 🌐 Automatic Proxy Discovery (for people who don't know proxies)

If you don't understand proxies or don't know which one is still alive, you don't have to test them by hand. Give odl a text file (or a URL to one) with one proxy per line, and it handles the rest:

```bash
# proxies.txt — one proxy per line; blank lines and # lines are ignored
# http://1.2.3.4:8080
# socks5://5.6.7.8:1080

odl --proxy-pool ~/proxies.txt "video URL"
```

odl tests each proxy with a real check (not just a ping), caches the first working one, and before every later download re-tests that same cached proxy first; if it's still alive, it skips the rest of the list entirely. If it died, it automatically scans the list again from the top.

```bash
# just check which proxies are alive right now, without downloading
odl --test-proxies --proxy-pool ~/proxies.txt

# set a default so you don't have to type --proxy-pool every time
odl --set proxy_pool_source=~/proxies.txt
odl "video URL"   # automatically uses that list from now on

# force it to ignore the cached proxy and re-scan the whole list
odl --proxy-pool-refresh "video URL"
```

⚠️ **Security note:** proxies from untrusted public sources can see, or even tamper with, your network traffic. odl only ever uses the source *you* give it — it never searches the internet for proxies on its own. Only point it at a source you trust.

---

## ⚙️ All CLI Options

| Option | Description |
|---|---|
| `-p, --playlist` | playlist mode |
| `-q, --quality` | 144/240/360/480/720/1080/1440/2160 |
| `-s, --sub-en` | English subtitles |
| `-fs, --sub-fa` | Persian subtitles (if available) |
| `-a, --audio-only` | audio only (mp3) |
| `-o, --output` | custom output directory |
| `-b, --batch` | concurrent downloads in playlist mode |
| `-x, --proxy` | proxy address, e.g. `socks5h://127.0.0.1:9050` |
| `--proxy-pool` | proxy list file/URL; automatic test, cache, and rotation |
| `--proxy-pool-refresh` | ignore the cache and re-scan the whole proxy list |
| `--test-proxies` | just check which proxies are alive, without downloading |
| `--player-client` | force a specific playback client (e.g. `android`) |
| `--bypass` | lighter/faster extraction |
| `--secure-cookies` | manually encrypt the current cookie file |
| `--reset-cookies` | delete the encrypted cookie file (forgot password) |
| `--import-cookies` | force a fresh cookie import |
| `--cookie-status` | show current cookie status |
| `--no-estimate` | skip size estimation (large playlists) |
| `--debug` | full debug info + traceback |
| `--doctor` | check installation health |
| `--check-update` | check for a yt-dlp update without installing |
| `--update` | update yt-dlp |
| `--version` | show version |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| `Sign in to confirm you're not a bot` | Cookie invalid/expired → `odl --import-cookies` |
| Region/geo error | Use `-x` or `--proxy-pool` with a proxy/Tor exit in an allowed country |
| Forgot master password | `odl --reset-cookies` and re-export |
| Not sure which proxy is alive | `odl --test-proxies --proxy-pool ~/proxies.txt` |
| Environment detection (`odl --doctor`) is wrong | `ODL_FORCE_ENVIRONMENT=kali_nethunter odl --doctor` (allowed values: `android_termux`, `kali_nethunter`, `desktop_linux`, `wsl`, `other`) |
| Not sure what's wrong | `odl --doctor` and `odl --debug "URL"` |

---

## 🗑️ Uninstallation

```bash
rm -f ~/.local/bin/odl
rm -rf ~/.config/opendl
rm -f ~/cookies.txt
```

---

## 🧭 Roadmap

Background auto-update · multiple cookie profiles · download history · interactive mode · speed limiting · scheduled downloads · duplicate detection · completion notifications · JSON output · automated tests (pytest)

---

## 📄 License

MIT — see [LICENSE](LICENSE).
