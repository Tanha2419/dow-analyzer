#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smc_report.py — گزارش فارسی و نمودار موتور Smart Money
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from tabulate import tabulate

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

LINE = "=" * 74
THIN = "-" * 74


def _bar(v: float, lo: float = 0, hi: float = 100, w: int = 22) -> str:
    f = int(np.clip((v - lo) / (hi - lo), 0, 1) * w)
    return "[" + "#" * f + "." * (w - f) + "]"


def _money(x: float) -> str:
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f}B$"
    if abs(x) >= 1e6:
        return f"{x / 1e6:.1f}M$"
    return f"{x:,.0f}$"


def _t(ts) -> str:
    try:
        return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M") if pd.Timestamp(ts).hour \
            else pd.Timestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return str(ts)


# ============================================================================
def print_smc_report(df: pd.DataFrame, res: Dict) -> None:
    price = float(df["Close"].iloc[-1])
    sig = res["signal"]
    st, liq, vp = res["struct"], res["liq"], res["vprof"]
    fl, hft, fake, coal = res["flow"], res["hft"], res["fake"], res["coalition"]
    n = len(df)

    print("\n\n" + LINE)
    print("   تحلیل پیشرفته پول هوشمند / ICT / جریان سفارش  —  داوجونز (DIA)")
    print(LINE)
    print(f"   تایم فریم: {res['interval']}   |   قیمت فعلی: ${price:,.2f}   |   "
          f"تعداد کندل: {n}")

    # ---------------- 1) ائتلاف بانک ها و HFT ----------------
    print("\n" + THIN)
    print(" 1) ائتلاف بانک ها و ردپای ربات های HFT")
    print(THIN)
    if coal.get("ok"):
        rows = []
        for m in coal["members"]:
            st_lbl = "انباشت" if m["strength"] > 0.12 else \
                     ("توزیع" if m["strength"] < -0.12 else "خنثی")
            rows.append([m["symbol"], m["name"], f"{m['ret_pct']:+.2f}%",
                         f"{m['vol_z']:+.2f}",
                         "بالای SMA20" if m["above_sma20"] else "زیر SMA20",
                         f"{m['strength']:+.2f}", st_lbl])
        print(tabulate(rows, headers=["نماد", "نهاد", "بازده 10K",
                                      "Z حجم", "موقعیت", "قدرت", "وضعیت"],
                       tablefmt="fancy_grid"))
        print(f"   امتیاز ائتلاف : {coal['score']:+.3f}   "
              f"{_bar(coal['score'] * 50 + 50)}")
        print(f"   درجه هماهنگی  : {coal['agreement'] * 100:.0f}%  "
              f"(هرچه بالاتر، جریان سفارش نهادی هماهنگ تر)")
        print(f"   سهم حجم سنگین : {coal['heavy_vol_share'] * 100:.0f}% از اعضا")
        if coal.get("corr_xlf") is not None:
            print(f"   همبستگی با بخش مالی: {coal['corr_xlf']:+.2f}")
        print(f"   >> جمع بندی: {coal['verdict']}")
    else:
        print("   داده ائتلاف بانک ها در دسترس نبود.")

    print(f"\n   شاخص فعالیت HFT : {hft['hft_index']:.0f}/100  {_bar(hft['hft_index'])}")
    print(f"   * جذب نقدینگی بدون حرکت قیمت : {hft['n_absorb']} کندل "
          f"({hft['burst_rate'] * 100:.0f}%)")
    print(f"   * کندل های شکار استاپ        : {hft['n_hunt']} کندل "
          f"({hft['hunt_rate'] * 100:.0f}%)")
    print(f"   * خودهمبستگی بازده           : {hft['autocorr']:+.3f}")
    print(f"   * میخکوب شدن روی اعداد رند   : {hft['pin_rate'] * 100:.0f}%")
    print(f"   >> رژیم الگوریتمی: {hft['regime']}")

    # ---------------- 2) FVG / BOS / CHoCH ----------------
    print("\n" + THIN)
    print(" 2) ساختار بازار: BOS / CHoCH / FVG / بلوک سفارش")
    print(THIN)
    ev = st["events"][-6:]
    if ev:
        rows = [[_t(e["time"]), e["type"],
                 "صعودی" if e["dir"] == "bull" else "نزولی",
                 f"${e['level']:,.2f}",
                 "ادامه روند" if e["type"] == "BOS" else "تغییر کاراکتر / بازگشت"]
                for e in ev]
        print(tabulate(rows, headers=["زمان", "رویداد", "جهت", "سطح شکسته", "مفهوم"],
                       tablefmt="fancy_grid"))
    bias_lbl = "صعودی" if st["bias"] > 0 else ("نزولی" if st["bias"] < 0 else "خنثی")
    print(f"   بایاس ساختاری فعلی: {bias_lbl}")
    if res.get("htf_bias") is not None:
        h = res["htf_bias"]
        print(f"   بایاس تایم فریم بالاتر: "
              f"{'صعودی' if h > 0 else ('نزولی' if h < 0 else 'خنثی')}")

    act = [g for g in res["fvgs"] if not g["filled"] and g["i"] > n - 120]
    act = sorted(act, key=lambda g: abs((g["top"] + g["bottom"]) / 2 - price))[:6]
    if act:
        rows = []
        for g in act:
            mid = (g["top"] + g["bottom"]) / 2
            rows.append([_t(g["time"]),
                         "صعودی (حمایتی)" if g["dir"] == "bull" else "نزولی (مقاومتی)",
                         f"${g['bottom']:,.2f} - ${g['top']:,.2f}",
                         f"{g['atr_x']:.2f}x ATR",
                         "لمس شده" if g["mitigated"] else "دست نخورده",
                         f"{(mid - price) / price * 100:+.2f}%"])
        print("\n   شکاف های قیمتی فعال (FVG) — مغناطیس قیمت:")
        print(tabulate(rows, headers=["زمان", "نوع", "محدوده", "اندازه",
                                      "وضعیت", "فاصله"], tablefmt="fancy_grid"))

    ob = [b for b in res["obs"] if not b["mitigated"] and b["i"] > n - 120]
    ob = sorted(ob, key=lambda b: abs((b["top"] + b["bottom"]) / 2 - price))[:5]
    if ob:
        rows = [[_t(b["time"]),
                 "صعودی (تقاضا)" if b["dir"] == "bull" else "نزولی (عرضه)",
                 f"${b['bottom']:,.2f} - ${b['top']:,.2f}",
                 f"{b['disp_atr']:.2f}x ATR", f"{b['vol_z']:+.2f}",
                 f"{((b['top'] + b['bottom']) / 2 - price) / price * 100:+.2f}%"]
                for b in ob]
        print("\n   بلوک های سفارش دست نخورده (ردپای مستقیم موسسات):")
        print(tabulate(rows, headers=["زمان", "نوع", "محدوده", "قدرت حرکت",
                                      "Z حجم", "فاصله"], tablefmt="fancy_grid"))

    # ---------------- 3) نقدینگی و گره حجمی ----------------
    print("\n" + THIN)
    print(" 3) تسویه نقدینگی، گره حجمی و اصلاح به گره")
    print(THIN)
    if vp:
        pos = "داخل ناحیه ارزش (تعادل)" if vp["in_value"] else \
              ("بالای ناحیه ارزش (پریمیوم)" if price > vp["vah"]
               else "زیر ناحیه ارزش (تخفیف)")
        rows = [
            ["POC (پرحجم ترین گره)", f"${vp['poc']:,.2f}", f"{vp['poc_dist_pct']:+.2f}%",
             "مغناطیس اصلی قیمت"],
            ["VAH (سقف ناحیه ارزش)", f"${vp['vah']:,.2f}",
             f"{(vp['vah'] - price) / price * 100:+.2f}%", "مرز پریمیوم"],
            ["VAL (کف ناحیه ارزش)", f"${vp['val']:,.2f}",
             f"{(vp['val'] - price) / price * 100:+.2f}%", "مرز تخفیف"],
        ]
        if vp.get("near_hvn"):
            rows.append(["نزدیک ترین HVN", f"${vp['near_hvn']:,.2f}",
                         f"{(vp['near_hvn'] - price) / price * 100:+.2f}%",
                         "گره تعادل - مقصد اصلاح"])
        if vp.get("near_lvn"):
            rows.append(["نزدیک ترین LVN", f"${vp['near_lvn']:,.2f}",
                         f"{(vp['near_lvn'] - price) / price * 100:+.2f}%",
                         "خلاء نقدینگی - عبور سریع"])
        print(tabulate(rows, headers=["سطح", "قیمت", "فاصله", "مفهوم"],
                       tablefmt="fancy_grid"))
        print(f"   موقعیت فعلی قیمت: {pos}")

    fb = liq.get("fresh_bsl", [])[:4]
    fs = liq.get("fresh_ssl", [])[:4]
    if fb or fs:
        rows = []
        for x in fb:
            rows.append(["BSL (نقدینگی خرید)", f"${x['price']:,.2f}",
                         f"+{x['dist_pct']:.2f}%", x["hits"],
                         "سقف برابر (EQH)" if x["eq"] else "سقف سوئینگ",
                         "دست نخورده"])
        for x in fs:
            rows.append(["SSL (نقدینگی فروش)", f"${x['price']:,.2f}",
                         f"{x['dist_pct']:.2f}%", x["hits"],
                         "کف برابر (EQL)" if x["eq"] else "کف سوئینگ",
                         "دست نخورده"])
        print("\n   استخرهای نقدینگی دست نخورده (اهداف احتمالی پول هوشمند):")
        print(tabulate(rows, headers=["نوع", "قیمت", "فاصله", "تعداد برخورد",
                                      "ساختار", "وضعیت"], tablefmt="fancy_grid"))

    if liq.get("periodic"):
        rows = [[k, f"${v['high']:,.2f}", f"{(v['high'] - price) / price * 100:+.2f}%",
                 f"${v['low']:,.2f}", f"{(v['low'] - price) / price * 100:+.2f}%"]
                for k, v in liq["periodic"].items()]
        print("\n   سطوح دوره ای (استخرهای اصلی نقدینگی ICT):")
        print(tabulate(rows, headers=["دوره", "سقف", "فاصله", "کف", "فاصله"],
                       tablefmt="fancy_grid"))

    # ---------------- 4) داده موسسات / پول هوشمند ----------------
    print("\n" + THIN)
    print(" 4) داده موسسات و جریان پول هوشمند (ICT Smart Money)")
    print(THIN)
    rows = [
        ["دلتای تجمعی (فشار خرید/فروش)", f"{fl['cd_slope']:+.3f}",
         "خریدار تهاجمی غالب" if fl["cd_slope"] > 0.02 else
         ("فروشنده تهاجمی غالب" if fl["cd_slope"] < -0.02 else "متعادل")],
        ["OBV (حجم متوازن)", f"{fl['obv_slope']:+.3f}",
         "صعودی" if fl["obv_slope"] > 0.02 else
         ("نزولی" if fl["obv_slope"] < -0.02 else "خنثی")],
        ["A/D (انباشت/توزیع)", f"{fl['ad_slope']:+.3f}",
         "انباشت" if fl["ad_slope"] > 0.02 else
         ("توزیع" if fl["ad_slope"] < -0.02 else "خنثی")],
        ["CMF (جریان پول چایکین)", f"{fl['cmf_last']:+.3f}",
         "ورود پول" if fl["cmf_last"] > 0.05 else
         ("خروج پول" if fl["cmf_last"] < -0.05 else "خنثی")],
        ["MFI (شاخص جریان نقدینگی)", f"{fl['mfi_last']:.1f}",
         "اشباع خرید" if fl["mfi_last"] > 78 else
         ("اشباع فروش" if fl["mfi_last"] < 25 else "نرمال")],
        ["VWAP نهادی (60 کندل)", f"${fl['vwap']:,.2f}",
         f"قیمت {fl['vwap_dev_pct']:+.2f}% نسبت به میانگین نهادی"],
    ]
    if fl.get("smi_trend") is not None:
        rows.append(["شاخص پول هوشمند (SMI)", f"{fl['smi_trend']:+.3f}",
                     "موسسات در حال خرید (ساعات پایانی)" if fl["smi_trend"] > 0
                     else "موسسات در حال فروش (ساعات پایانی)"])
    print(tabulate(rows, headers=["شاخص نهادی", "مقدار", "تفسیر"],
                   tablefmt="fancy_grid"))
    print(f"   >> واگرایی قیمت با جریان سفارش: {fl['divergence']}")

    # ---------------- 5) روند فیک ----------------
    print("\n" + THIN)
    print(" 5) تشخیص روند فیک")
    print(THIN)
    print(f"   امتیاز فیک بودن: {fake['score']:.0f}/100  {_bar(fake['score'])}")
    print(f"   ADX: {fake['adx']:.1f}   |   کارایی حرکت: {fake['efficiency'] * 100:.0f}%"
          f"   |   شکست های جعلی: {fake['fake_breaks']}")
    if fake["reasons"]:
        print("   شواهد:")
        for r in fake["reasons"]:
            print(f"     * {r}")
    else:
        print("     * شاهد قابل توجهی از فیک بودن یافت نشد")
    print(f"   >> {fake['verdict']}")

    # ---------------- 6) سفارشات سنگین ----------------
    print("\n" + THIN)
    print(" 6) سفارشات سنگین و حجم های عمده")
    print(THIN)
    bl = res["blocks"]
    if bl["n_blocks"]:
        rows = [[_t(b["time"]),
                 "خرید عمده" if b["side"] == "BUY" else
                 ("فروش عمده" if b["side"] == "SELL" else "خنثی"),
                 f"{b['vol'] / 1e6:.2f}M", f"{b['vol_z']:+.2f}",
                 _money(b["notional"]), f"${b['price']:,.2f}",
                 f"{b['ret_pct']:+.2f}%"]
                for b in bl["blocks"][:7]]
        print(tabulate(rows, headers=["زمان", "سمت", "حجم", "Z حجم",
                                      "ارزش معامله", "قیمت", "بازده کندل"],
                       tablefmt="fancy_grid"))
        print(f"   ارزش خرید عمده : {_money(bl['buy_notional'])}")
        print(f"   ارزش فروش عمده : {_money(bl['sell_notional'])}")
        print(f"   نامتوازنی سفارش: {bl['imbalance'] * 100:+.1f}%  "
              f"{_bar(bl['imbalance'] * 50 + 50)}")
        if bl["absorption"]:
            print(f"   جذب سفارش (دیوار نهادی): {len(bl['absorption'])} مورد — "
                  + ", ".join(f"${a['price']:,.2f}" for a in bl["absorption"][:4]))
        if bl["icebergs"]:
            print(f"   سفارش آیسبرگ (تقسیم شده): {len(bl['icebergs'])} مورد — "
                  + ", ".join(f"${i['price']:,.2f} ({i['side']})"
                              for i in bl["icebergs"][:4]))
    else:
        print("   سفارش سنگین غیرعادی در بازه اخیر شناسایی نشد.")

    # ---------------- 7) Sweep ----------------
    print("\n" + THIN)
    print(" 7) جمع آوری نقدینگی بازار (BSL / SSL Sweep)")
    print(THIN)
    sw = res["sweeps"][-7:]
    if sw:
        rows = [[_t(s["time"]),
                 "شکار سقف (BSL)" if s["type"] == "BSL_SWEEP" else "شکار کف (SSL)",
                 f"${s['level']:,.2f}", f"${s['extreme']:,.2f}",
                 f"{s['depth_atr']:.2f} ATR", f"{s['wick'] * 100:.0f}%",
                 f"{s['vol_z']:+.2f}",
                 "نزولی" if s["dir"] == "bear" else "صعودی"]
                for s in sw]
        print(tabulate(rows, headers=["زمان", "نوع", "سطح هدف", "حد نفوذ",
                                      "عمق", "سایه", "Z حجم", "پیامد"],
                       tablefmt="fancy_grid"))
        last = sw[-1]
        bars = n - 1 - last["i"]
        print(f"   >> آخرین شکار نقدینگی {bars} کندل قبل رخ داده — "
              f"{'سوگیری صعودی بعد از جمع آوری استاپ فروشندگان' if last['dir'] == 'bull' else 'سوگیری نزولی بعد از جمع آوری استاپ خریداران'}")
    else:
        print("   شکار نقدینگی فعالی در بازه اخیر ثبت نشد.")

    # ---------------- سیگنال نهایی ----------------
    print("\n" + LINE)
    print("   سیگنال نهایی پول هوشمند")
    print(LINE)
    arrow = "^^^" if sig["direction"] > 0 else ("vvv" if sig["direction"] < 0 else "---")
    print(f"   {arrow}  {sig['label']}   |   درجه کیفیت: {sig['grade']}")
    print(f"   امتیاز خالص : {sig['score']:+.1f}   (خام: {sig['raw_score']:+.1f})")
    print(f"   اطمینان     : {sig['confidence']:.0f}%  {_bar(sig['confidence'])}")
    print(f"   ضریب اصلاح  : روند فیک x{sig['fake_penalty']:.2f}  |  "
          f"محیط HFT x{sig['hft_penalty']:.2f}")

    print("\n   تجزیه امتیاز بر اساس فاکتورهای پول هوشمند:")
    rows = [[p[0], f"{p[1]:+.1f}",
             ("صعودی" if p[1] > 0 else ("نزولی" if p[1] < 0 else "خنثی")), p[2]]
            for p in sig["parts"]]
    print(tabulate(rows, headers=["فاکتور", "وزن", "جهت", "جزئیات"],
                   tablefmt="fancy_grid"))

    if sig["plan"]:
        p = sig["plan"]
        side = "خرید" if sig["direction"] > 0 else "فروش"
        rows = [
            ["نوع موقعیت", side + (" (لانگ)" if sig["direction"] > 0 else " (شورت)")],
            ["نقطه ورود", f"${p['entry']:,.2f}" +
             ("  (ورود در بازار)" if p["at_market"] else "  (سفارش لیمیت در ناحیه)")],
            ["حد ضرر", f"${p['stop']:,.2f}   ({p['risk_pct']:.2f}% ریسک)"],
            ["هدف اول (TP1)", f"${p['tp1']:,.2f}   نسبت سود به زیان {p['rr1']:.2f}"],
            ["هدف دوم (TP2)", f"${p['tp2']:,.2f}   نسبت سود به زیان {p['rr2']:.2f}"],
            ["هدف سوم (TP3)", f"${p['tp3']:,.2f}   نسبت سود به زیان {p['rr3']:.2f}"],
        ]
        print("\n   طرح معاملاتی پیشنهادی:")
        print(tabulate(rows, headers=["پارامتر", "مقدار"], tablefmt="fancy_grid"))
        print("   * مدیریت پیشنهادی: 50% در TP1 خروج، حد ضرر به نقطه سربه سر، "
              "مابقی تا TP2/TP3")
        print("   * حجم پیشنهادی: ریسک هر معامله حداکثر 1 تا 2 درصد کل سرمایه")
    else:
        print("\n   >> شرایط ورود فراهم نیست. منتظر یکی از این تاییدها بمانید:")
        print("      * شکار نقدینگی (Sweep) روی یک استخر دست نخورده")
        print("      * سپس CHoCH یا BOS هم جهت در ساختار")
        print("      * همراه با تایید دلتای تجمعی و سفارشات سنگین")
    print(LINE)


# ============================================================================
def plot_smc(df: pd.DataFrame, res: Dict, interval: str = "1d",
             bars: int = 140) -> Path:
    d = df.tail(min(bars, len(df))).copy()
    off = len(df) - len(d)
    x = np.arange(len(d))
    price = float(df["Close"].iloc[-1])
    sig, vp, liq = res["signal"], res["vprof"], res["liq"]

    fig = plt.figure(figsize=(19, 13))
    gs = fig.add_gridspec(4, 2, width_ratios=[5, 1],
                          height_ratios=[3.1, 0.85, 0.85, 0.85],
                          hspace=0.12, wspace=0.03)
    ax = fig.add_subplot(gs[0, 0])
    axv = fig.add_subplot(gs[0, 1], sharey=ax)
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax)
    ax4 = fig.add_subplot(gs[3, 0], sharex=ax)

    fig.suptitle(
        f"Smart Money / ICT / Order Flow  —  DIA (Dow Jones)  |  {interval}  |  "
        f"${price:,.2f}\nSignal: {sig['label']}   Score {sig['score']:+.1f}   "
        f"Confidence {sig['confidence']:.0f}%   Grade {sig['grade']}",
        fontsize=14, fontweight="bold")

    # ---------- کندل استیک ----------
    o = d["Open"].to_numpy(float)
    h = d["High"].to_numpy(float)
    l = d["Low"].to_numpy(float)
    c = d["Close"].to_numpy(float)
    for i in range(len(d)):
        up = c[i] >= o[i]
        col = "#26A69A" if up else "#EF5350"
        ax.plot([i, i], [l[i], h[i]], color=col, lw=0.8, zorder=2)
        ax.add_patch(Rectangle((i - 0.32, min(o[i], c[i])), 0.64,
                               max(abs(c[i] - o[i]), 1e-6),
                               facecolor=col, edgecolor=col, lw=0.5, zorder=3))

    # ---------- FVG ----------
    for g in res["fvgs"]:
        j = g["i"] - off
        if j < 0 or g["filled"]:
            continue
        col = "#00E676" if g["dir"] == "bull" else "#FF5252"
        ax.add_patch(Rectangle((j, g["bottom"]), len(d) - j, g["top"] - g["bottom"],
                               facecolor=col, alpha=0.13, edgecolor=col,
                               lw=0.6, ls=":", zorder=1))

    # ---------- Order Block ----------
    for b in res["obs"]:
        j = b["i"] - off
        if j < 0 or b["mitigated"]:
            continue
        col = "#1E88E5" if b["dir"] == "bull" else "#8E24AA"
        ax.add_patch(Rectangle((j, b["bottom"]), len(d) - j, b["top"] - b["bottom"],
                               facecolor=col, alpha=0.16, edgecolor=col,
                               lw=1.0, zorder=1))
        ax.text(j + 0.5, b["top"], " OB", color=col, fontsize=7,
                fontweight="bold", va="bottom", zorder=6)

    # ---------- BOS / CHoCH ----------
    for e in res["struct"]["events"]:
        j = e["i"] - off
        if j < 0:
            continue
        col = "#00C853" if e["dir"] == "bull" else "#D50000"
        r = max(e["ref_i"] - off, 0)
        ax.plot([r, j], [e["level"], e["level"]], color=col, lw=1.2,
                ls="--", alpha=0.85, zorder=4)
        ax.text(j, e["level"], f" {e['type']}", color=col, fontsize=8,
                fontweight="bold",
                va="bottom" if e["dir"] == "bull" else "top", zorder=6)

    # ---------- Sweep ----------
    for s in res["sweeps"]:
        j = s["i"] - off
        if j < 0:
            continue
        if s["dir"] == "bull":
            ax.scatter([j], [s["extreme"]], marker="^", s=190, c="#00E676",
                       edgecolors="#004D40", lw=1.2, zorder=7)
            ax.text(j, s["extreme"], "SSL\nsweep", color="#00C853", fontsize=6.5,
                    ha="center", va="top", fontweight="bold", zorder=7)
        else:
            ax.scatter([j], [s["extreme"]], marker="v", s=190, c="#FF1744",
                       edgecolors="#4A0000", lw=1.2, zorder=7)
            ax.text(j, s["extreme"], "BSL\nsweep", color="#D50000", fontsize=6.5,
                    ha="center", va="bottom", fontweight="bold", zorder=7)

    # ---------- سفارشات سنگین ----------
    for b in res["blocks"]["blocks"][:12]:
        j = b["i"] - off
        if j < 0:
            continue
        col = "#FFD600" if b["side"] == "BUY" else "#FF6D00"
        ax.scatter([j], [b["price"]], marker="D", s=55, c=col,
                   edgecolors="black", lw=0.7, zorder=8, alpha=0.95)

    # ---------- سطوح نقدینگی ----------
    for q in liq.get("fresh_bsl", [])[:4]:
        ax.axhline(q["price"], color="#FF5252", ls=":", lw=1.1, alpha=0.75, zorder=2)
        ax.text(len(d) - 1, q["price"], f"  BSL ${q['price']:,.1f}", color="#FF5252",
                fontsize=7.5, va="bottom", zorder=6)
    for q in liq.get("fresh_ssl", [])[:4]:
        ax.axhline(q["price"], color="#00E676", ls=":", lw=1.1, alpha=0.75, zorder=2)
        ax.text(len(d) - 1, q["price"], f"  SSL ${q['price']:,.1f}", color="#00C853",
                fontsize=7.5, va="top", zorder=6)

    if vp:
        ax.axhline(vp["poc"], color="#FFC107", lw=1.8, alpha=0.9, zorder=3)
        ax.text(0, vp["poc"], f" POC ${vp['poc']:,.1f}", color="#FF8F00",
                fontsize=9, fontweight="bold", va="bottom", zorder=6)
        ax.axhspan(vp["val"], vp["vah"], color="#FFC107", alpha=0.06, zorder=0)

    # ---------- طرح معامله ----------
    if sig["plan"]:
        p = sig["plan"]
        ax.axhline(p["entry"], color="#2962FF", lw=1.6, zorder=5)
        ax.axhline(p["stop"], color="#D50000", lw=1.4, ls="--", zorder=5)
        for k, tp in enumerate([p["tp1"], p["tp2"], p["tp3"]], 1):
            ax.axhline(tp, color="#00C853", lw=1.1, ls="-.", alpha=0.8, zorder=5)
            ax.text(len(d) * 0.35, tp, f"TP{k} ${tp:,.1f}", color="#00A040",
                    fontsize=8, fontweight="bold", va="bottom", zorder=6)
        ax.text(len(d) * 0.35, p["entry"], f"ENTRY ${p['entry']:,.1f}",
                color="#2962FF", fontsize=8.5, fontweight="bold",
                va="bottom", zorder=6)
        ax.text(len(d) * 0.35, p["stop"], f"SL ${p['stop']:,.1f}",
                color="#D50000", fontsize=8.5, fontweight="bold",
                va="top", zorder=6)

    ax.set_ylabel("Price ($)", fontsize=10)
    ax.grid(alpha=0.18)
    ax.set_xlim(-1, len(d) + 1)
    hnd = [
        plt.Line2D([], [], color="#00E676", marker="^", ls="", ms=9, label="SSL Sweep"),
        plt.Line2D([], [], color="#FF1744", marker="v", ls="", ms=9, label="BSL Sweep"),
        plt.Line2D([], [], color="#FFD600", marker="D", ls="", ms=7, label="Block Order"),
        plt.Line2D([], [], color="#1E88E5", lw=6, alpha=0.4, label="Order Block"),
        plt.Line2D([], [], color="#00E676", lw=6, alpha=0.3, label="FVG"),
        plt.Line2D([], [], color="#FFC107", lw=2, label="POC / Value Area"),
        plt.Line2D([], [], color="#00C853", ls="--", label="BOS / CHoCH"),
    ]
    ax.legend(handles=hnd, loc="upper left", fontsize=8, ncol=2, framealpha=0.9)

    # ---------- پروفایل حجم افقی ----------
    if vp:
        ctr, prof = vp["centers"], vp["profile"]
        m = (ctr >= l.min() * 0.995) & (ctr <= h.max() * 1.005)
        cols = ["#FFC107" if abs(cc - vp["poc"]) < 1e-9 else
                ("#66BB6A" if vp["val"] <= cc <= vp["vah"] else "#78909C")
                for cc in ctr[m]]
        axv.barh(ctr[m], prof[m], height=(ctr[1] - ctr[0]) * 0.9, color=cols, alpha=0.8)
        for lv in vp["lvn"]:
            if l.min() <= lv <= h.max():
                axv.axhline(lv, color="#E040FB", lw=0.8, ls=":", alpha=0.8)
        axv.set_xticks([])
        axv.tick_params(labelleft=False)
        axv.set_title("Volume\nProfile", fontsize=8)
        axv.grid(alpha=0.12)

    # ---------- حجم و سفارشات سنگین ----------
    v = d["Volume"].to_numpy(float)
    vcol = ["#26A69A" if c[i] >= o[i] else "#EF5350" for i in range(len(d))]
    ax2.bar(x, v, color=vcol, alpha=0.65, width=0.75)
    ax2.plot(x, pd.Series(v).rolling(20).mean(), color="#2962FF", lw=1.1,
             label="Vol MA20")
    for b in res["blocks"]["blocks"][:12]:
        j = b["i"] - off
        if j >= 0:
            ax2.scatter([j], [b["vol"]], marker="*", s=130,
                        c="#FFD600" if b["side"] == "BUY" else "#FF6D00",
                        edgecolors="black", lw=0.5, zorder=5)
    ax2.set_ylabel("Volume", fontsize=9)
    ax2.legend(loc="upper left", fontsize=7)
    ax2.grid(alpha=0.15)

    # ---------- دلتای تجمعی ----------
    from smart_money import delta_proxy
    cd = np.cumsum(delta_proxy(d))
    ax3.plot(x, cd, color="#7B1FA2", lw=1.5, label="Cumulative Delta")
    ax3.fill_between(x, cd, 0, where=cd >= 0, color="#26A69A", alpha=0.22)
    ax3.fill_between(x, cd, 0, where=cd < 0, color="#EF5350", alpha=0.22)
    ax3.axhline(0, color="gray", lw=0.6)
    ax3.set_ylabel("Cum Delta", fontsize=9)
    ax3.legend(loc="upper left", fontsize=7)
    ax3.grid(alpha=0.15)

    # ---------- CMF + فیک ----------
    cmf = res["flow"]["cmf"][-len(d):]
    ax4.bar(x, cmf, color=["#26A69A" if q > 0 else "#EF5350" for q in cmf],
            alpha=0.7, width=0.8)
    ax4.axhline(0, color="gray", lw=0.6)
    ax4.axhline(0.05, color="#26A69A", ls="--", lw=0.6, alpha=0.6)
    ax4.axhline(-0.05, color="#EF5350", ls="--", lw=0.6, alpha=0.6)
    ax4.set_ylabel("CMF(20)", fontsize=9)
    ax4.grid(alpha=0.15)
    ax4.text(0.995, 0.06,
             f"Fake-Trend Risk: {res['fake']['score']:.0f}/100   |   "
             f"HFT Activity: {res['hft']['hft_index']:.0f}/100",
             transform=ax4.transAxes, ha="right", fontsize=9, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.35", fc="#FFF9C4", ec="#F9A825"))

    step = max(1, len(d) // 14)
    ticks = list(range(0, len(d), step))
    labels = [pd.Timestamp(d.index[i]).strftime(
        "%m-%d" if interval == "1d" else "%m-%d %H:%M") for i in ticks]
    ax4.set_xticks(ticks)
    ax4.set_xticklabels(labels, rotation=42, ha="right", fontsize=8)
    for a in (ax, ax2, ax3):
        a.tick_params(labelbottom=False)

    out = OUTPUT_DIR / f"smc_analysis_{interval}.png"
    plt.savefig(out, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"\n[+] نمودار پول هوشمند ذخیره شد: {out}")
    return out
