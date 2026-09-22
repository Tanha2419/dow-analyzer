# -*- coding: utf-8 -*-
"""راه انداز گام به گام گوگل شیت.

اجرا:  python gsheet_setup.py

توکن می سازد، فایل تنظیمات را پر می کند، اتصال را می آزماید و
داده ها را می فرستد. هیچ چیز در چت یا بیرون از دستگاه شما نمی رود.
"""
from __future__ import annotations

import io
import os
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "gsheet.env")
GS = os.path.join(HERE, "gsheet", "AppsScript.gs")


def hr(t=""):
    print("\n" + "=" * 56)
    if t:
        print(t)
        print("=" * 56)


def main() -> int:
    hr("راه اندازی پشتیبان گوگل شیت")
    print("""
این ابزار شما را گام به گام می برد. هر چیزی که وارد می کنید
فقط روی همین دستگاه ذخیره می شود.
""")

    # گام ۱: توکن
    hr("گام ۱ از ۴ — ساخت توکن")
    token = secrets.token_urlsafe(32)
    print("\nتوکن تصادفی ساخته شد:\n")
    print("    " + token + "\n")
    print("این رشته را کپی کنید — در گام بعد لازم است.")

    # گام ۲: کد آماده
    hr("گام ۲ از ۴ — آماده سازی کد اسکریپت")
    try:
        code = io.open(GS, encoding="utf-8").read()
    except Exception as e:
        print("خطا: فایل AppsScript.gs پیدا نشد: %s" % e)
        return 1

    filled = code.replace("var TOKEN = 'TOKEN_HERE';",
                          "var TOKEN = '%s';" % token)
    out = os.path.join(HERE, "gsheet", "AppsScript.READY.gs")
    io.open(out, "w", encoding="utf-8").write(filled)

    print("""
یک نسخه با توکن پرشده ساخته شد:

    gsheet/AppsScript.READY.gs

کارهای شما:
  ۱. sheets.new را باز کنید (یک شیت خالی بسازید)
  ۲. Extensions ← Apps Script
  ۳. همه کد آنجا را پاک کنید
  ۴. محتویات AppsScript.READY.gs را بچسبانید
  ۵. Ctrl+S
  ۶. Deploy ← New deployment ← چرخ دنده ← Web app
       Execute as    : Me
       Who has access: Anyone
  ۷. Deploy ← Authorize ← Advanced ← Go to... ← Allow
  ۸. آدرسی که می دهد را کپی کنید
""")
    try:
        input("وقتی آماده شد Enter بزنید... ")
    except EOFError:
        pass

    # گام ۳: آدرس
    hr("گام ۳ از ۴ — وارد کردن آدرس")
    url = ""
    for _ in range(3):
        try:
            url = input("\nآدرس برنامه وب را بچسبانید:\n> ").strip()
        except EOFError:
            print("\nورودی تمام شد.")
            return 1
        if not url:
            print("خالی بود.")
            continue
        if not url.startswith("https://script.google.com/"):
            print("هشدار: آدرس باید با https://script.google.com/ شروع شود.")
            continue
        if url.endswith("/dev"):
            print("هشدار: این آدرس /dev است (نسخه آزمایشی).")
            print("   آدرس /exec لازم است — از Deploy / Manage deployments.")
            continue
        if not url.endswith("/exec"):
            print("هشدار: آدرس معمولا به /exec ختم می شود. مطمئنید؟")
            try:
                ans = input("   ادامه؟ (y/n) ").lower()
            except EOFError:
                return 1
            if ans != "y":
                continue
        break
    else:
        print("\nآدرس معتبر وارد نشد. بعدا دوباره اجرا کنید.")
        return 1

    io.open(ENV, "w", encoding="utf-8").write(
        "GSHEET_URL=%s\nGSHEET_TOKEN=%s\n" % (url, token))
    try:
        os.chmod(ENV, 0o600)
    except Exception:
        pass
    print("\nOK — در gsheet.env ذخیره شد (در gitignore است)")

    # گام ۴: آزمون
    hr("گام ۴ از ۴ — آزمون اتصال")
    sys.path.insert(0, HERE)
    os.environ["GSHEET_URL"] = url
    os.environ["GSHEET_TOKEN"] = token
    try:
        import gsync
    except Exception as e:
        print("خطا: gsync بارگذاری نشد: %s" % e)
        return 1

    print("\nآزمون اتصال...")
    r = gsync.ping()
    if not r.get("ok"):
        print("ناموفق: %s" % r.get("error"))
        print("""
چند علت رایج:
  - «Who has access» روی Anyone نیست
  - نسخه جدید منتشر نشده (Manage deployments / ویرایش / Version: New)
  - آدرس /exec نیست
""")
        return 1
    if not r.get("authorized"):
        print("ناموفق: برنامه وب زنده است ولی توکن پذیرفته نشد.")
        print("   یعنی توکن داخل اسکریپت با این یکی فرق دارد.")
        print("   AppsScript.READY.gs را دوباره بچسبانید و نسخه جدید منتشر کنید.")
        return 1

    print("OK — اتصال برقرار، %s سطر در شیت" % r.get("rows"))

    print("\nارسال داده ها...")
    p = gsync.push()
    if not p.get("ok"):
        print("ناموفق: %s" % p.get("error"))
        return 1
    print("OK — %d سطر جدید، %d به روز" % (
        p.get("created", 0), p.get("updated", 0)))

    print("\nآزمون تکرار (نباید سطر تکراری بسازد)...")
    p2 = gsync.push()
    if p2.get("ok") and p2.get("created", 0) == 0:
        print("OK — تایید شد: %d به روز، صفر تکراری" % p2.get("updated", 0))
    else:
        print("هشدار: نتیجه غیرمنتظره: %s" % p2)

    hr("تمام شد")
    print("""
شیت شما آماده است و داده ها رفتند.

برای اجرای خودکار ابری، این دو را در گیت هاب اضافه کنید:
  Settings / Secrets and variables / Actions / New repository secret

  نام: GSHEET_URL     مقدار: (همان آدرس)
  نام: GSHEET_TOKEN   مقدار: (داخل فایل gsheet.env)

برای دیدن مقادیر:  cat gsheet.env

توجه: فایل AppsScript.READY.gs توکن دارد — آن را جایی نفرستید.
      اگر خواستید پاکش کنید:  rm gsheet/AppsScript.READY.gs
""")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nلغو شد.")
        sys.exit(130)
