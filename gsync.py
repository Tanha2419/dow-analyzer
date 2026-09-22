# -*- coding: utf-8 -*-
"""همگام سازی ژورنال با گوگل شیت — پشتیبان بیرونی.

طراحی:
  • آدرس و توکن فقط از متغیر محیطی خوانده می شوند، هرگز از کد
  • شکست همگام سازی نباید ثبت را خراب کند — همیشه بی صدا رد می شود
  • همه رکوردها هر بار فرستاده می شوند (۶ کیلوبایت ناچیز است)
    و سمت شیت بر اساس id به روز می شوند، پس تکراری ساخته نمی شود

تنظیم:
    export GSHEET_URL='https://script.google.com/macros/s/..../exec'
    export GSHEET_TOKEN='...'
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

TIMEOUT = 45
MAX_ROWS = 400          # هر درخواست؛ بیشتر از این ممکن است به سقف ۳۰ ثانیه بخورد


def _read_env_file(path: str) -> Dict[str, str]:
    """خواندن ساده فایل KEY=VALUE بدون وابستگی بیرونی."""
    out: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip("'\"")
    except Exception:
        pass
    return out


def _cfg() -> tuple:
    """اولویت: متغیر محیطی، سپس gsheet.env، سپس .env

    این ترتیب عمدی است — در گیت هاب اکشنز متغیر محیطی از Secrets
    می آید و باید بر فایل محلی اولویت داشته باشد.
    """
    url = os.environ.get("GSHEET_URL", "").strip()
    tok = os.environ.get("GSHEET_TOKEN", "").strip()
    if url and tok:
        return url, tok

    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("gsheet.env", ".env"):
        d = _read_env_file(os.path.join(here, name))
        url = url or d.get("GSHEET_URL", "").strip()
        tok = tok or d.get("GSHEET_TOKEN", "").strip()
        if url and tok:
            break
    return url, tok


def enabled() -> bool:
    url, tok = _cfg()
    return bool(url and tok)


def _post(url: str, payload: Dict) -> Dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "dow-analyzer/1.0"})
    # اپس اسکریپت با ۳۰۲ به googleusercontent هدایت می کند؛
    # urllib خودش دنبال می کند ولی باید POST را نگه دارد
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except Exception:
        return dict(ok=False, error="پاسخ غیر JSON: " + raw[:160])


def push(rows: Optional[List[Dict]] = None, quiet: bool = True) -> Dict:
    """ارسال رکوردها به شیت. هرگز استثنا پرتاب نمی کند."""
    url, tok = _cfg()
    if not url or not tok:
        return dict(ok=False, skipped=True, error="GSHEET_URL/TOKEN تنظیم نشده")

    if rows is None:
        try:
            import journal as jr
            rows = jr._load()
        except Exception as e:
            return dict(ok=False, error="خواندن ژورنال: %s" % str(e)[:120])

    if not rows:
        return dict(ok=True, created=0, updated=0, note="ژورنال خالی")

    created = updated = 0
    try:
        for i in range(0, len(rows), MAX_ROWS):
            chunk = rows[i:i + MAX_ROWS]
            res = _post(url, dict(token=tok, rows=chunk))
            if not res.get("ok"):
                return dict(ok=False, error=res.get("error", "?"))
            created += int(res.get("created") or 0)
            updated += int(res.get("updated") or 0)
        out = dict(ok=True, created=created, updated=updated, sent=len(rows))
        if not quiet:
            print("  گوگل شیت: %d جدید، %d به روز" % (created, updated))
        return out
    except urllib.error.HTTPError as e:
        return dict(ok=False, error="HTTP %s" % e.code)
    except Exception as e:
        return dict(ok=False, error=str(e)[:150])


def ping() -> Dict:
    """آزمون اتصال بدون نوشتن."""
    url, tok = _cfg()
    if not url or not tok:
        return dict(ok=False, error="GSHEET_URL/TOKEN تنظیم نشده")
    try:
        sep = "&" if "?" in url else "?"
        req = urllib.request.Request(
            url + sep + "token=" + urllib.parse.quote(tok),
            headers={"User-Agent": "dow-analyzer/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return dict(ok=False, error=str(e)[:150])


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ping"
    if not enabled():
        print("❌ GSHEET_URL و GSHEET_TOKEN تنظیم نشده اند.")
        print("   راهنما: gsheet/GSHEET.md")
        sys.exit(1)
    if cmd == "ping":
        r = ping()
        if r.get("ok") and r.get("authorized"):
            print("✅ اتصال برقرار — %s سطر در شیت" % r.get("rows"))
        elif r.get("ok"):
            print("⚠️  برنامه وب زنده است ولی توکن پذیرفته نشد")
        else:
            print("❌ %s" % r.get("error"))
            sys.exit(1)
    else:
        r = push(quiet=False)
        if r.get("ok"):
            print("✅ %d جدید · %d به روز · %d ارسال" % (
                r.get("created", 0), r.get("updated", 0), r.get("sent", 0)))
        else:
            print("❌ %s" % r.get("error"))
            sys.exit(1)
