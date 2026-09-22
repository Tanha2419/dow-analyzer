# -*- coding: utf-8 -*-
"""اجرای تک شات ثبت سیگنال — برای GitHub Actions.

با autolog.py فرق دارد: آن یک نخ همیشه در حال اجراست، این یک بار
اجرا می شود، ثبت می کند و خارج می شود. مناسب محیط cron.

خروج با کد صفر حتی وقتی چیزی ثبت نشد (بازار بسته) — تا اکشن
بی دلیل قرمز نشود. فقط خطای واقعی کد غیرصفر می دهد.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

TARGETS = [("XAUUSD", "1h"), ("US30", "1h"),
           ("XAUUSD", "1d"), ("US30", "1d")]


def log(msg: str) -> None:
    print("[%s] %s" % (
        datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def main() -> int:
    t0 = time.time()
    log("شروع ثبت دوره ای")

    try:
        import assets as A
        import agent
        import journal as jr
    except Exception:
        log("خطای import:")
        traceback.print_exc()
        return 1

    before = len(jr._load())
    log("ژورنال پیش از اجرا: %d نمونه" % before)

    recorded, skipped, failed = 0, 0, 0
    for asset, iv in TARGETS:
        try:
            st = A.market_state(asset)
            is_open = st.get("is_open") if isinstance(st, dict) else True
            if not is_open:
                label = (st.get("status_fa") or st.get("label") or "بسته"
                         ) if isinstance(st, dict) else "?"
                log("رد %-6s %-3s — بازار %s" % (asset, iv, label))
                skipped += 1
                continue

            out = agent.decide(iv, asset=asset, with_ml=False, with_mtf=False)
            sc = float((out.get("decision") or {}).get("score") or 0)
            if abs(sc) < 1.0:
                log("رد %-6s %-3s — امتیاز %+.2f زیر آستانه" % (asset, iv, sc))
                skipped += 1
                continue

            recorded += 1
            log("ثبت %-6s %-3s — امتیاز %+.2f" % (asset, iv, sc))
        except Exception as e:
            failed += 1
            log("خطا %-6s %-3s — %s" % (asset, iv, str(e)[:110]))

    # ارزیابی سیگنال های رسیده به افق
    try:
        ev = jr.evaluate()
        n = int(ev.get("newly_checked") or 0)
        log("ارزیابی: %d سیگنال تازه سنجیده شد" % n)
        if ev.get("n"):
            log("  کارنامه: %d نمونه · نرخ برد %s٪ · میانگین R %s" % (
                ev.get("n"), ev.get("win_rate"), ev.get("avg_r")))
    except Exception as e:
        log("خطای ارزیابی: %s" % str(e)[:110])

    after = len(jr._load())
    log("ژورنال پس از اجرا: %d نمونه (+%d)" % (after, after - before))

    # پشتیبان گوگل شیت — کاملا اختیاری.
    # اگر تنظیم نشده یا شکست خورد، ثبت نباید آسیب ببیند.
    try:
        import gsync
        if gsync.enabled():
            g = gsync.push()
            if g.get("ok"):
                log("گوگل شیت: %d جدید · %d به روز" % (
                    g.get("created", 0), g.get("updated", 0)))
            else:
                log("گوگل شیت ناموفق (نادیده گرفته شد): %s"
                    % str(g.get("error"))[:90])
        else:
            log("گوگل شیت: تنظیم نشده — رد شد")
    except Exception as e:
        log("گوگل شیت خطا (نادیده گرفته شد): %s" % str(e)[:90])
    log("پایان در %.1f ثانیه — ثبت %d · رد %d · خطا %d" % (
        time.time() - t0, recorded, skipped, failed))

    # خلاصه برای صفحه خلاصه اکشن
    smry = os.environ.get("GITHUB_STEP_SUMMARY")
    if smry:
        try:
            s = jr.summary()
            with open(smry, "a", encoding="utf-8") as f:
                f.write("### ثبت دوره ای\n\n")
                f.write("| مورد | مقدار |\n|---|---|\n")
                f.write("| ثبت شده این اجرا | %d |\n" % recorded)
                f.write("| رد شده | %d |\n" % skipped)
                f.write("| کل نمونه ها | %d |\n" % s.get("total_recorded", 0))
                f.write("| ارزیابی شده | %d |\n" % s.get("n", 0))
                if s.get("win_rate") is not None:
                    f.write("| نرخ برد | %s٪ |\n" % s["win_rate"])
                    f.write("| میانگین R | %s |\n" % s.get("avg_r"))
        except Exception:
            pass

    # فقط وقتی همه چیز خطا داد شکست بخور
    if failed == len(TARGETS):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
