# -*- coding: utf-8 -*-
"""بررسی آمادگی استقرار — قبل از push اجرا کنید.

هر چیزی که می تواند استقرار را بی سروصدا خراب کند اینجا آزموده
می شود: فایل های لازم، نشت اسرار، و اجرای واقعی مسیر ثبت.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

OK, BAD, WARN = "✅", "❌", "⚠️ "
problems = 0


def check(cond, good: str, bad: str, fatal: bool = True) -> bool:
    global problems
    if cond:
        print("  %s %s" % (OK, good))
        return True
    print("  %s %s" % (BAD if fatal else WARN, bad))
    if fatal:
        problems += 1
    return False


print("\n═══ ۱. فایل های لازم ═══")
need = ["cron_record.py", "journal.py", "agent.py", "assets.py",
        ".github/workflows/record.yml", "requirements.txt"]
for f in need:
    check(os.path.exists(f), "%s موجود" % f, "%s پیدا نشد" % f)

print("\n═══ ۲. نشت اسرار ═══")
check(not os.path.exists(".git") or
      subprocess.run(["git", "check-ignore", "-q", ".env"],
                     capture_output=True).returncode == 0
      if os.path.exists(".git") else True,
      ".env در gitignore است", ".env در gitignore نیست — خطر نشت کلید!")

gi = io.open(".gitignore", encoding="utf-8").read() if os.path.exists(
    ".gitignore") else ""
check(".env" in gi, ".gitignore شامل .env", ".gitignore فاقد .env")

# آیا کلیدی داخل کد hard-code شده؟
leaks = []
for f in os.listdir("."):
    if not f.endswith(".py") or f == os.path.basename(__file__):
        continue  # خود این فایل الگوها را به عنوان متن دارد
    try:
        t = io.open(f, encoding="utf-8").read()
    except Exception:
        continue
    import re
    # انتساب یک رشته غیرتهی به متغیر کلید = نشت واقعی
    pat = re.compile(r"""(FINNHUB|ALPHAVANTAGE|FRED)_KEY\s*=\s*["'][^"']{8,}["']""")
    for line in t.splitlines():
        if pat.search(line) and "environ" not in line and "getenv" not in line:
            leaks.append("%s: %s" % (f, line.strip()[:60]))
check(not leaks, "کلیدی در کد hard-code نشده",
      "کلید در کد پیدا شد: %s" % leaks[:2])

print("\n═══ ۳. ورک فلو ═══")
try:
    import yaml
    d = yaml.safe_load(io.open(".github/workflows/record.yml",
                               encoding="utf-8").read())
    k = True if True in d else "on"
    check("schedule" in d[k], "زمان بندی تعریف شده", "زمان بندی ندارد")
    check("workflow_dispatch" in d[k],
          "اجرای دستی ممکن است", "اجرای دستی ندارد", fatal=False)
    check(d.get("permissions", {}).get("contents") == "write",
          "دسترسی نوشتن دارد", "دسترسی نوشتن ندارد — commit شکست می خورد")
    steps = d["jobs"]["record"]["steps"]
    check(any("git add -f journal.jsonl" in str(s.get("run", ""))
              for s in steps),
          "journal.jsonl با -f اضافه می شود",
          "journal.jsonl در gitignore می ماند و ذخیره نمی شود")
except ImportError:
    print("  %s pyyaml نصب نیست — بررسی ورک فلو رد شد" % WARN)
except Exception as e:
    print("  %s خطای خواندن ورک فلو: %s" % (BAD, e))
    problems += 1

print("\n═══ ۴. اجرای واقعی مسیر ثبت ═══")
try:
    import assets as A
    import journal as jr
    before = len(jr._load())
    _orig = A.market_state
    A.market_state = lambda a: dict(is_open=True, status_fa="آزمایشی")
    import cron_record
    rc = cron_record.main()
    A.market_state = _orig
    after = len(jr._load())
    check(rc == 0, "کد خروج صفر", "کد خروج %d" % rc)
    check(after >= before, "ژورنال سالم ماند (%d نمونه)" % after,
          "ژورنال کوچک شد!")
except Exception as e:
    print("  %s اجرا شکست خورد: %s" % (BAD, str(e)[:120]))
    problems += 1

print("\n═══ ۵. پشتیبان گوگل شیت (اختیاری) ═══")
try:
    import gsync
    if not gsync.enabled():
        print("  %s تنظیم نشده — رد شد (اختیاری است)" % WARN)
        print("     راهنما: gsheet/GSHEET.md")
    else:
        r = gsync.ping()
        if r.get("ok") and r.get("authorized"):
            print("  %s اتصال برقرار — %s سطر در شیت" % (OK, r.get("rows")))
        elif r.get("ok"):
            print("  %s برنامه وب زنده است ولی توکن پذیرفته نشد" % BAD)
            problems += 1
        else:
            print("  %s %s" % (BAD, r.get("error")))
            problems += 1
except Exception as e:
    print("  %s بررسی شیت ممکن نشد: %s" % (WARN, str(e)[:80]))

print("\n" + "═" * 46)
if problems:
    print("%s %d مشکل — قبل از push رفع کنید" % (BAD, problems))
    sys.exit(1)
print("%s آماده استقرار" % OK)
sys.exit(0)
