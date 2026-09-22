# -*- coding: utf-8 -*-
"""ساخت journal.csv از journal.jsonl — برای باز کردن مستقیم در گوگل شیت.

بدون توکن، بدون Apps Script، بدون هیچ نصبی.
گوگل شیت: File ← Import ← Upload ← journal.csv
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "journal.jsonl")
OUT = os.path.join(HERE, "journal.csv")

COLS = [
    ("id", "شناسه"), ("ts", "زمان ثبت"), ("asset", "دارایی"),
    ("interval", "تایم فریم"), ("price", "قیمت ورود"),
    ("score", "امتیاز"), ("conf", "اطمینان"), ("grade", "نمره"),
    ("label", "تصمیم"), ("allowed", "مجاز"), ("bucket", "کندل"),
    ("updates", "تکرار"), ("checked", "ارزیابی شده"),
    ("outcome_r", "نتیجه R"), ("outcome_status", "وضعیت نتیجه"),
]


def build() -> dict:
    if not os.path.exists(SRC):
        return dict(ok=False, error="journal.jsonl پیدا نشد")

    rows = []
    for line in io.open(SRC, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue

    # تازه ترین بالا
    rows.sort(key=lambda r: str(r.get("ts") or ""), reverse=True)

    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([fa for _, fa in COLS])
        for r in rows:
            o = r.get("outcome") or {}
            w.writerow([
                r.get("id", ""), r.get("ts", ""), r.get("asset", ""),
                r.get("interval", ""), r.get("price", ""),
                r.get("score", ""), r.get("conf", ""), r.get("grade", ""),
                r.get("label", ""),
                "بله" if r.get("allowed") else "خیر",
                r.get("bucket", ""), r.get("updates", 1),
                "بله" if r.get("checked") else "خیر",
                o.get("r_mult", ""),
                o.get("status", "") or ("" if r.get("checked") else "در انتظار"),
            ])

    return dict(ok=True, rows=len(rows), path=OUT,
                size=os.path.getsize(OUT))


if __name__ == "__main__":
    r = build()
    if not r.get("ok"):
        print("خطا: %s" % r.get("error"))
        sys.exit(1)
    print("journal.csv ساخته شد — %d سطر، %d بایت" % (r["rows"], r["size"]))
