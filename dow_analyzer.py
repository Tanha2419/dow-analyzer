#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ابزار تحلیل تکنیکال و بکتست داوجونز (نماد DIA - ETF شاخص داوجونز)
- داده زنده و تاریخی از Yahoo Finance (رایگان، بدون کلید API)
- اندیکاتورهای SMA/EMA/RSI/MACD/Bollinger/ATR/Volume
- تشخیص خودکار حمایت/مقاومت + فیبوناچی
- سیگنال خرید/فروش
- بکتست استراتژی ترند فالو
"""

import os, sys, warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from tabulate import tabulate

# --- موتور پول هوشمند / ICT / جریان سفارش ---
import smart_money as smc
from smc_report import print_smc_report, plot_smc
from smc_backtest import run_smc_backtest

warnings.filterwarnings("ignore")
sns.set_style("darkgrid")
plt.rcParams["figure.figsize"] = (14, 10)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

SYMBOL = "DIA"
INTERVAL_PERIODS = {
    "1m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "1h":  "730d",
    "1d":  "5y",
}


# ---------- دریافت داده ----------
def fetch_data(interval="1d", period=None):
    if period is None:
        period = INTERVAL_PERIODS.get(interval, "1y")
    print(f"\n[+] دریافت داده {SYMBOL} | تایم فریم {interval} | دوره {period}")
    df = yf.Ticker(SYMBOL).history(interval=interval, period=period)
    if df.empty:
        print("[!] خطا: داده ای دریافت نشد.")
        sys.exit(1)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    print(f"    {len(df)} کندل | از {df.index[0].date()} تا {df.index[-1]}")
    print(f"    آخرین قیمت: ${df['Close'].iloc[-1]:,.2f}")
    return df


# ---------- اندیکاتورها ----------
def add_indicators(df):
    print("[+] محاسبه اندیکاتورها...")
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    df["SMA_20"]  = ta.sma(c, 20)
    df["SMA_50"]  = ta.sma(c, 50)
    df["SMA_200"] = ta.sma(c, 200)
    df["EMA_12"]  = ta.ema(c, 12)
    df["EMA_26"]  = ta.ema(c, 26)
    df["RSI"]     = ta.rsi(c, 14)
    macd = ta.macd(c, 12, 26, 9)
    df["MACD"]        = macd.iloc[:, 0]
    df["MACD_Signal"] = macd.iloc[:, 1]
    df["MACD_Hist"]   = macd.iloc[:, 2]
    bb = ta.bbands(c, 20, 2)
    df["BB_Upper"] = bb.iloc[:, 0]
    df["BB_Mid"]   = bb.iloc[:, 1]
    df["BB_Lower"] = bb.iloc[:, 2]
    df["ATR"]       = ta.atr(h, l, c, 14)
    df["Vol_SMA20"] = ta.sma(v, 20)
    return df


# ---------- حمایت و مقاومت ----------
def find_sr(df, window=5):
    levels = []
    for i in range(window, len(df) - window):
        if df["High"].iloc[i] == df["High"].iloc[i-window:i+window+1].max():
            levels.append(("R", df["High"].iloc[i]))
        if df["Low"].iloc[i]  == df["Low"].iloc[i-window:i+window+1].min():
            levels.append(("S", df["Low"].iloc[i]))
    supports, resistances = [], []
    for kind, p in sorted(levels, key=lambda x: x[1]):
        group = supports if kind == "S" else resistances
        if group and abs(p - group[-1]) / group[-1] < 0.01:
            group[-1] = (group[-1] + p) / 2
        else:
            group.append(p)
    cur = df["Close"].iloc[-1]
    supports    = sorted([p for p in supports if p < cur], reverse=True)[:3]
    resistances = sorted([p for p in resistances if p > cur])[:3]
    return supports, resistances


# ---------- فیبوناچی ----------
def fib_levels(df, lookback=120):
    r = df.tail(lookback)
    hi, lo = r["High"].max(), r["Low"].min()
    d = hi - lo
    return {
        "0% (کف)":     lo,
        "23.6%":       lo + 0.236*d,
        "38.2%":       lo + 0.382*d,
        "50%":         lo + 0.500*d,
        "61.8%":       lo + 0.618*d,
        "78.6%":       lo + 0.786*d,
        "100% (سقف)":  hi,
    }


# ---------- سیگنال ها ----------
def generate_signals(df):
    df["Signal"] = 0
    buy = (df["RSI"] < 30) & (df["Close"] <= df["BB_Lower"]*1.005) & \
          (df["MACD"] > df["MACD_Signal"]) & (df["MACD"].shift(1) <= df["MACD_Signal"].shift(1))
    sell = (df["RSI"] > 70) & (df["Close"] >= df["BB_Upper"]*0.995) & \
           (df["MACD"] < df["MACD_Signal"]) & (df["MACD"].shift(1) >= df["MACD_Signal"].shift(1))
    df.loc[buy,  "Signal"] = 1
    df.loc[sell, "Signal"] = -1
    return df


# ---------- نمودار ----------
def plot_analysis(df, sup, res, fib, interval):
    pdf = df.tail(min(250, len(df))).copy()
    cp  = pdf["Close"].iloc[-1]
    fig, axes = plt.subplots(4, 1, figsize=(16, 14),
                             gridspec_kw={"height_ratios": [3,1,1,1]}, sharex=True)
    fig.suptitle(f"تحلیل تکنیکال DIA (داوجونز) — تایم فریم {interval}\n"
                 f"آخرین قیمت: ${cp:,.2f} | {datetime.now():%Y-%m-%d %H:%M}",
                 fontsize=14, fontweight="bold")
    ax = axes[0]
    ax.plot(pdf.index, pdf["Close"], "#2196F3", lw=1.5, label="Close")
    ax.plot(pdf.index, pdf["SMA_20"], "#FF9800", lw=1, label="SMA20", alpha=0.8)
    ax.plot(pdf.index, pdf["SMA_50"], "#9C27B0", lw=1, label="SMA50", alpha=0.8)
    ax.plot(pdf.index, pdf["BB_Upper"], "#F44336", lw=0.7, ls="--", alpha=0.5)
    ax.plot(pdf.index, pdf["BB_Lower"], "#4CAF50", lw=0.7, ls="--", alpha=0.5)
    ax.fill_between(pdf.index, pdf["BB_Upper"], pdf["BB_Lower"], color="#2196F3", alpha=0.05)
    for p in sup:
        ax.axhline(p, color="#4CAF50", ls=":", alpha=0.7, lw=1)
        ax.text(pdf.index[-1], p, f"  S ${p:,.0f}", color="#4CAF50", fontsize=9, va="bottom")
    for p in res:
        ax.axhline(p, color="#F44336", ls=":", alpha=0.7, lw=1)
        ax.text(pdf.index[-1], p, f"  R ${p:,.0f}", color="#F44336", fontsize=9, va="top")
    b = pdf[pdf["Signal"] == 1]
    s = pdf[pdf["Signal"] == -1]
    ax.scatter(b.index, b["Close"]*0.99, marker="^", c="#00C853", s=150, label="Buy", zorder=5)
    ax.scatter(s.index, s["Close"]*1.01, marker="v", c="#D50000", s=150, label="Sell", zorder=5)
    ax.set_ylabel("Price ($)"); ax.legend(loc="upper left", fontsize=9); ax.grid(alpha=0.3)
    ax = axes[1]
    clrs = ["#4CAF50" if c >= o else "#F44336" for c,o in zip(pdf["Close"], pdf["Open"])]
    ax.bar(pdf.index, pdf["Volume"], color=clrs, alpha=0.6, width=0.8)
    ax.plot(pdf.index, pdf["Vol_SMA20"], "#2196F3", lw=1, label="Vol MA20")
    ax.set_ylabel("Volume"); ax.legend(loc="upper left", fontsize=9)
    ax = axes[2]
    ax.plot(pdf.index, pdf["RSI"], "#673AB7", lw=1.2)
    ax.axhline(70, color="#F44336", ls="--", alpha=0.5)
    ax.axhline(30, color="#4CAF50", ls="--", alpha=0.5)
    ax.fill_between(pdf.index, 30, 70, color="#9E9E9E", alpha=0.1)
    ax.set_ylim(0,100); ax.set_ylabel("RSI(14)")
    ax.text(pdf.index[-1], pdf["RSI"].iloc[-1], f" {pdf['RSI'].iloc[-1]:.1f}", fontsize=9)
    ax = axes[3]
    ax.plot(pdf.index, pdf["MACD"], "#2196F3", lw=1, label="MACD")
    ax.plot(pdf.index, pdf["MACD_Signal"], "#FF9800", lw=1, label="Signal")
    hc = ["#4CAF50" if h >= 0 else "#F44336" for h in pdf["MACD_Hist"]]
    ax.bar(pdf.index, pdf["MACD_Hist"], color=hc, alpha=0.5, width=0.8)
    ax.axhline(0, color="gray", lw=0.5)
    ax.set_ylabel("MACD"); ax.legend(loc="upper left", fontsize=9)
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    out = OUTPUT_DIR / f"dow_analysis_{interval}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight"); plt.close()
    print(f"[+] نمودار ذخیره شد: {out}")


# ---------- استراتژی بکتست ----------
def _crossunder(a, b):
    return a[-2] >= b[-2] and a[-1] < b[-1]

class DowTrendStrategy(Strategy):
    """استراتژی ترند فالوینگ:
    ورود 1: کراس طلایی SMA20 روی SMA50
    ورود 2: پولبک قیمت به SMA20 در روند صعودی (SMA20 > SMA50) با RSI مناسب
    خروج: کراس مرگ یا RSI در ناحیه بیش خرید
    """
    sma_fast = 20
    sma_slow = 50
    rsi_low  = 45
    rsi_high = 70
    atr_sl   = 2.5
    atr_tp   = 4.0

    def init(self):
        df = self.data.df
        self.sma_f = self.I(lambda v: v, df["SMA_20"].values, name="SMA20", overlay=True)
        self.sma_s = self.I(lambda v: v, df["SMA_50"].values, name="SMA50", overlay=True)
        self.rsi   = self.I(lambda v: v, df["RSI"].values,    name="RSI")
        self.atr   = self.I(lambda v: v, df["ATR"].values,    name="ATR")

    def next(self):
        if any(np.isnan(x[-1]) for x in (self.sma_f, self.sma_s, self.rsi, self.atr)):
            return
        price = self.data.Close[-1]
        atr   = self.atr[-1]

        if not self.position:
            golden_cross = crossover(self.sma_f, self.sma_s)
            pullback_buy = (self.sma_f[-1] > self.sma_s[-1] and
                            price <= self.sma_f[-1] * 1.01 and
                            price >= self.sma_f[-2] and
                            self.rsi[-1] > self.rsi_low and
                            self.rsi[-1] < self.rsi_high)
            if golden_cross or pullback_buy:
                self.buy(sl=price - self.atr_sl*atr, tp=price + self.atr_tp*atr)
        else:
            if _crossunder(self.sma_f, self.sma_s) or self.rsi[-1] > self.rsi_high:
                self.position.close()


def run_backtest(df, cash=100_000, commission=0.001):
    print("\n" + "="*60)
    print(" در حال اجرای بکتست (5 سال اخیر، روزانه)")
    print("="*60)
    cols = ["Open","High","Low","Close","Volume","SMA_20","SMA_50","RSI","ATR"]
    bt_df = df[cols].dropna().copy()
    bt = Backtest(bt_df, DowTrendStrategy, cash=cash, commission=commission,
                  margin=1, trade_on_close=True, exclusive_orders=True)
    stats = bt.run()
    eq = stats["_equity_curve"]

    def fm(v): return f"${v:,.0f}"  if isinstance(v,(int,float)) and not np.isnan(v) else "N/A"
    def fp(v): return f"{v:+,.2f}%" if isinstance(v,(int,float)) and not np.isnan(v) else "N/A"
    def fn(v): return f"{v:.2f}"    if isinstance(v,(int,float)) and not np.isnan(v) else "N/A"
    def fi(v): return f"{int(v)}"   if isinstance(v,(int,float)) and not np.isnan(v) else "N/A"

    rows = [
        ["بازه زمانی",            f"{eq.index[0].date()} -> {eq.index[-1].date()}"],
        ["سرمایه اولیه",          fm(cash)],
        ["سرمایه نهایی",          fm(stats.get("Equity Final [$]"))],
        ["بازده کل",              fp(stats.get("Return [%]"))],
        ["بازده خرید و نگهداری",  fp(stats.get("Buy & Hold Return [%]"))],
        ["بازده سالانه (CAGR)",   fp(stats.get("Return (Ann.) [%]"))],
        ["حداکثر افت سرمایه",     fp(stats.get("Max. Drawdown [%]"))],
        ["میانگین سود معامله",    fp(stats.get("Avg. Trade [%]"))],
        ["بهترین معامله",         fp(stats.get("Best Trade [%]"))],
        ["بدترین معامله",         fp(stats.get("Worst Trade [%]"))],
        ["تعداد معاملات",         fi(stats.get("# Trades"))],
        ["نرخ برد",               fp(stats.get("Win Rate [%]"))],
        ["فاکتور سود",            fn(stats.get("Profit Factor"))],
        ["نسبت شارپ",             fn(stats.get("Sharpe Ratio"))],
        ["نسبت سورتینو",          fn(stats.get("Sortino Ratio"))],
        ["نسبت کالمار",           fn(stats.get("Calmar Ratio"))],
    ]
    print("\n" + tabulate(rows, headers=["شاخص", "مقدار"], tablefmt="fancy_grid"))

    bt_path = OUTPUT_DIR / "backtest_report.html"
    try:
        bt.plot(open_browser=False, filename=str(bt_path))
        print(f"\n[+] گزارش HTML بکتست: {bt_path}")
    except Exception as e:
        print(f"    (ذخیره HTML با خطا مواجه شد: {e})")

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(eq.index, eq["Equity"], "#2196F3", lw=1.5, label="Equity Curve")
    ax.set_title("منحنی سرمایه — استراتژی داوجونز", fontweight="bold")
    ax.set_ylabel("Capital ($)"); ax.grid(alpha=0.3); ax.legend()
    plt.tight_layout()
    eq_path = OUTPUT_DIR / "equity_curve.png"
    plt.savefig(eq_path, dpi=150); plt.close()
    print(f"[+] منحنی سرمایه: {eq_path}")


# ---------- گزارش ترمینال ----------
def print_summary(df, sup, res, fib):
    last, prev = df.iloc[-1], df.iloc[-2]
    chg = last["Close"] - prev["Close"]
    chg_pct = chg/prev["Close"]*100
    print("\n" + "="*60)
    print(" خلاصه وضعیت داوجونز (DIA)")
    print("="*60)
    print(f" زمان:       {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f" قیمت:       ${last['Close']:,.2f}  ({chg:+.2f} / {chg_pct:+.2f}%)")
    print(f" دامنه روز:  ${last['Low']:,.2f} - ${last['High']:,.2f}")
    print(f" حجم:        {last['Volume']:,.0f}  (MA20: {last['Vol_SMA20']:,.0f})")
    rsi_st = "بیش خرید" if last["RSI"]>70 else ("بیش فروش" if last["RSI"]<30 else "خنثی")
    trend  = "صعودی"   if last["SMA_20"]>last["SMA_50"] else "نزولی"
    macd_s = "صعودی"   if last["MACD"]>last["MACD_Signal"] else "نزولی"
    bb_pos = (last["Close"]-last["BB_Lower"])/(last["BB_Upper"]-last["BB_Lower"])*100
    print(f"\n اندیکاتورها:")
    print(f"   * RSI(14):      {last['RSI']:.1f} -> {rsi_st}")
    print(f"   * SMA20/SMA50:  {last['SMA_20']:,.2f} / {last['SMA_50']:,.2f} -> {trend}")
    print(f"   * MACD:         {last['MACD']:.2f} vs {last['MACD_Signal']:.2f} -> {macd_s}")
    print(f"   * Bollinger:    موقعیت {bb_pos:.0f}%")
    print(f"   * ATR(14):      {last['ATR']:.2f}")
    print(f"\n حمایت ها:")
    for p in sup:  print(f"   * ${p:,.2f} ({(p-last['Close'])/last['Close']*100:.1f}%)")
    print(f" مقاومت ها:")
    for p in res:  print(f"   * ${p:,.2f} (+{(p-last['Close'])/last['Close']*100:.1f}%)")
    print(f"\n فیبوناچی (120 کندل اخیر):")
    for n,p in fib.items():
        m = "  << قیمت" if abs(p-last["Close"])/last["Close"] < 0.01 else ""
        print(f"   * {n:12s}: ${p:,.2f}{m}")
    buys  = df.tail(20)[df.tail(20)["Signal"]==1]
    sells = df.tail(20)[df.tail(20)["Signal"]==-1]
    print(f"\n سیگنال های اخیر (20 کندل):")
    if not buys.empty:
        for i,r in buys.iterrows():  print(f"   خرید: {i}  ${r['Close']:,.2f}")
    if not sells.empty:
        for i,r in sells.iterrows(): print(f"   فروش: {i}  ${r['Close']:,.2f}")
    if buys.empty and sells.empty:
        print("   * سیگنال قطعی وجود ندارد - منتظر تایید بمانید")
    score = 0
    score += 1 if last["SMA_20"]>last["SMA_50"] else -1
    score += 1 if last["RSI"]<40 else (-1 if last["RSI"]>70 else 0)
    score += 1 if last["MACD"]>last["MACD_Signal"] else -1
    score += 1 if last["Close"]>last["BB_Mid"] else -1
    if score >= 2:   verdict = "متمایل به صعود - شرایط لانگ مناسب تر"
    elif score <=-2: verdict = "متمایل به نزول - احتیاط در لانگ"
    else:            verdict = "خنثی / سایدوی - منتظر شکست سطوح کلیدی"
    print(f"\n جمع بندی: {verdict}")
    print("="*60)


# ---------- main ----------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="تحلیل تکنیکال + پول هوشمند (ICT) + بکتست داوجونز")
    ap.add_argument("-i", "--interval", default="1d",
                    choices=list(INTERVAL_PERIODS.keys()), help="تایم فریم")
    ap.add_argument("-p", "--period", default=None, help="بازه داده (مثل 1y, 2y, max)")
    ap.add_argument("--cash", type=float, default=100_000, help="سرمایه اولیه بکتست")
    ap.add_argument("--no-classic", action="store_true",
                    help="رد کردن تحلیل کلاسیک")
    ap.add_argument("--no-smc", action="store_true",
                    help="رد کردن تحلیل پول هوشمند")
    ap.add_argument("--no-backtest", action="store_true", help="رد کردن بکتست")
    ap.add_argument("--no-coalition", action="store_true",
                    help="رد کردن تحلیل ائتلاف بانک ها (سریع تر)")
    ap.add_argument("--long-only", action="store_true",
                    help="بکتست فقط لانگ (بدون شورت)")
    ap.add_argument("--no-regime", action="store_true",
                    help="غیرفعال کردن فیلتر رژیم بازار در بکتست")
    args = ap.parse_args()

    df = fetch_data(args.interval, args.period)
    df = add_indicators(df)
    sup, res_lv = find_sr(df)
    fib = fib_levels(df)
    df = generate_signals(df)

    # ---------------- 1) تحلیل کلاسیک ----------------
    if not args.no_classic:
        plot_analysis(df, sup, res_lv, fib, args.interval)
        print_summary(df, sup, res_lv, fib)

    # ---------------- 2) تحلیل پول هوشمند / ICT ----------------
    if not args.no_smc:
        htf_df = None
        intraday = None
        try:
            if args.interval == "1d":
                htf_df = yf.Ticker(SYMBOL).history(interval="1wk", period="5y")
                htf_df.index = pd.to_datetime(htf_df.index)
                if htf_df.index.tz is not None:
                    htf_df.index = htf_df.index.tz_localize(None)
                intraday = yf.Ticker(SYMBOL).history(interval="30m", period="60d")
            else:
                htf_df = yf.Ticker(SYMBOL).history(interval="1d", period="2y")
                htf_df.index = pd.to_datetime(htf_df.index)
                if htf_df.index.tz is not None:
                    htf_df.index = htf_df.index.tz_localize(None)
                intraday = df
        except Exception as e:
            print(f"    (داده تایم فریم بالاتر دریافت نشد: {e})")

        print("\n[+] اجرای موتور پول هوشمند (Smart Money / ICT / Order Flow)...")
        smc_res = smc.run_full_smc(df, args.interval, htf_df=htf_df,
                                   intraday=intraday,
                                   with_coalition=not args.no_coalition)
        print_smc_report(df, smc_res)
        plot_smc(df, smc_res, args.interval)

    # ---------------- 3) بکتست ----------------
    if not args.no_backtest:
        if args.interval == "1d":
            df_bt = add_indicators(fetch_data("1d", "5y"))
            run_backtest(df_bt, cash=args.cash)
            run_smc_backtest(df_bt, cash=args.cash, interval="1d",
                             long_only=args.long_only,
                             regime_filter=not args.no_regime)
        else:
            run_smc_backtest(df, cash=args.cash, interval=args.interval,
                             long_only=args.long_only,
                             regime_filter=not args.no_regime)

    print(f"\n تحلیل کامل شد. خروجی ها: {OUTPUT_DIR.resolve()}/")
