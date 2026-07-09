# 📥 Open Downloader CLI

<div align="center">

**یک دانلودر یوتیوب ساده، امن و رزیوم‌پذیر برای خط فرمان**
**A simple, secure, resumable YouTube downloader for the command line**

بر پایه‌ی / Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) · دستور اجرا / Command: `odl`

**فارسی | [English ⬇](#-english)**

</div>

---

## 📚 فهرست مطالب

- [ویژگی‌ها](#-ویژگیها)
- [پیش‌نیازها](#-پیشنیازها)
- [نصب](#-نصب)
- [دریافت کوکی — راهنمای گام‌به‌گام](#-دریافت-کوکی--راهنمای-گامبهگام)
- [استفاده](#-استفاده)
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
| خطای Region/جغرافیایی | از `-x` با یه پروکسی/Tor در کشور مجاز استفاده کن |
| رمز اصلی یادت رفته | `odl --reset-cookies` و export مجدد |
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

## ✨ Features

| Feature | Description |
|---|---|
| 🎬 Single / playlist downloads | Live colored progress bars, concurrent playlist downloads |
| ⏸️ Automatic resume | Interrupted downloads (network drops, phone reboots) continue automatically |
| 🍪 Automatic cookie retrieval | Adapts to the environment — desktop, rooted Android, or plain Android |
| 🔐 Cookie encryption | AES (via Fernet) + a master password that is never stored anywhere |
| 🌐 Proxy/Tor support | Full SOCKS5/HTTP support |
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
| Region/geo error | Use `-x` with a proxy/Tor exit in an allowed country |
| Forgot master password | `odl --reset-cookies` and re-export |
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
