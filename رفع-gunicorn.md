# 🔧 رفع خطای «No module named gunicorn»

## پیام خطا

```
==> Build successful 🎉
==> Deploying...
==> Running 'python -m gunicorn wsgi:app --bind 0.0.0.0:$PORT ...'
/opt/render/project/src/.venv/bin/python: No module named gunicorn
==> Exited with status 1
```

---

## ⚡ راه‌حل — یک کادر، ۳۰ ثانیه، بدون آپلود

در رندر بروید به:

**Settings ← Build & Deploy ← Build Command ← Edit**

کادر را پاک کنید و **دقیقاً** این را بگذارید:

```
pip install -r requirements-web.txt
```

سپس **Save changes** ← بالای صفحه **Manual Deploy** ← **Deploy latest commit**

تمام. فایل `requirements-web.txt` از قبل در ریپوی شماست و `gunicorn` دارد.

---

## چرا این خطا رخ داد؟

دو کادر در رندر وجود دارد و من قبلاً فقط دومی را درست کرده بودم:

| کادر | مقدار فعلی شما | باید باشد |
|---|---|---|
| **Build Command** | `pip install -r requirements.txt` ❌ | `pip install -r requirements-web.txt` ✅ |
| **Start Command** | `python -m gunicorn wsgi:app ...` ✅ | همین درست است — دست نزنید |

**Build Command** تعیین می‌کند چه چیزی *نصب* شود.
**Start Command** تعیین می‌کند چه چیزی *اجرا* شود.

رندر داشت از `requirements.txt` نصب می‌کرد — فایلی که در نسخهٔ آپلودشدهٔ شما `gunicorn` نداشت. پس gunicorn هرگز نصب نشد و موقع اجرا پیدا نشد.

### اثبات از روی لاگ خودتان

| نشانه در لاگ | نتیجه‌گیری |
|---|---|
| `Build successful 🎉` | پایتون ۳.۱۲ کار کرد، `numba` ساخته شد ✅ |
| `No module named gunicorn` | `requirements-web.txt` نصب **نشده** ❌ |

هر دو با هم فقط یک معنا دارند: Build Command روی فایل اشتباه است.

---

## دو تفاوت مهم با خطای قبلی

این خطا **با `command not found` قبلی فرق دارد** — دقت کنید:

| پیام | معنی | رفع |
|---|---|---|
| `gunicorn: command not found` | نصب هست، ولی در PATH نیست | `python -m` اضافه کن ← ✅ انجام شد |
| `No module named gunicorn` | اصلاً **نصب نشده** | Build Command را عوض کن ← الان |

پس کار قبلی هدر نرفت — آن مشکل هم واقعاً وجود داشت و حل شد. این یک لایهٔ دیگر بود.

---

## سود جانبی این تغییر

با `requirements-web.txt` نصب سبک‌تر می‌شود:

| | requirements.txt | requirements-web.txt |
|---|---|---|
| حافظه | ~۳۸۰ مگابایت | **~۱۸۱ مگابایت** |
| زمان ساخت | ~۴ دقیقه | **~۹۰ ثانیه** |
| numba / pandas-ta | دارد (ریسک خطا) | ندارد |

سقف رایگان رندر ۵۱۲ مگابایت است — پس این تغییر حاشیهٔ امن را زیاد می‌کند.

---

## راه دوم (اگر Build Command را نمی‌خواهید دست بزنید)

بستهٔ جدید `dow-analyzer.zip` را آپلود کنید. در این نسخه `gunicorn` به **هر دو** فایل اضافه شده، پس با هر کدام از دو کادر کار می‌کند.

ولی راه اول سریع‌تر است و همین الان جواب می‌دهد.

---

## لاگ موفق چه شکلی است؟

```
==> Using Python version 3.12.7
==> Running build command 'pip install -r requirements-web.txt'...
Successfully installed flask gunicorn yfinance pandas numpy ...
==> Build successful 🎉
==> Deploying...
==> Running 'python -m gunicorn wsgi:app --bind 0.0.0.0:$PORT ...'
[INFO] Starting gunicorn 26.2.0
[INFO] Listening at: http://0.0.0.0:10000
[INFO] Booting worker with pid: 52
[+] موتور رصد زنده فعال شد
==> Your service is live 🎉
```

خط `[+] موتور رصد زنده فعال شد` یعنی موتور داخلی هم بالا آمده.

---

## بعد از سبز شدن

**۱. تست سلامت**

```
https://آدرس-شما.onrender.com/api/ping
```

باید ببینید: `{"ok":true,"pong":true,"ts":...}`

**۲. بیدار نگه داشتن (اختیاری ولی توصیه‌شده)**

سرویس رایگان بعد از ۱۵ دقیقه بی‌کاری می‌خوابد. در [uptimerobot.com](https://uptimerobot.com) یک مانیتور رایگان بسازید:

| تنظیم | مقدار |
|---|---|
| Monitor Type | HTTP(s) |
| URL | `https://آدرس-شما.onrender.com/api/ping` |
| Interval | ۵ دقیقه |

⚠️ **حتماً `/api/ping`** — هرگز آدرس اصلی (`/`). آدرس اصلی هر بار یک تحلیل کامل اجرا می‌کند و روزی ۲۸۸ درخواست بیهوده به یاهو می‌فرستد که به محدودیت نرخ می‌خورید.

---

## تاریخچهٔ کامل — چهار خطا تا اینجا

| # | خطا | علت | رفع |
|---|---|---|---|
| ۱ | `numba` build failed | پایتون ۳.۱۴ | `runtime.txt` = ۳.۱۲ |
| ۲ | `Cannot install on Python 3.14.3` | رندر `render.yaml` را نادیده گرفت | `runtime.txt` + `.python-version` |
| ۳ | `gunicorn: command not found` | PATH | `python -m gunicorn` |
| ۴ | `No module named gunicorn` | Build Command روی فایل اشتباه | `requirements-web.txt` ✅ |

---

## نکتهٔ یادگاری برای آینده

رندر برای سرویس‌هایی که **دستی** ساخته می‌شوند، `render.yaml` را **نادیده می‌گیرد**. هرچه در آن فایل بنویسید بی‌اثر است. تنظیمات واقعی فقط در صفحهٔ **Settings** داشبورد اعمال می‌شوند.

تنها استثنا: `runtime.txt` که همیشه خوانده می‌شود.
