"""
European Gas Storage Analysis
-----------------------------
Compares this year's EU gas storage fill level (%) with the range of the
previous 5 years, using daily data from GIE AGSI+ (https://agsi.gie.eu).

Usage:
    pip install pandas matplotlib requests
    python gas_storage.py            # downloads fresh data from AGSI+
    python gas_storage.py --offline  # uses the CSV saved in this repo

An AGSI+ API key is optional: set AGSI_KEY if you have one.
"""
import os
import sys
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd

CSV = "eu_gas_storage_2021_2026.csv"
THIS_YEAR = date.today().year
YEARS_BACK = 5


def download():
    """Download daily EU aggregate storage data from the AGSI+ API."""
    import requests

    headers = {"x-key": os.environ["AGSI_KEY"]} if "AGSI_KEY" in os.environ else {}
    rows, page, last = [], 1, 1
    while page <= last:
        r = requests.get(
            "https://agsi.gie.eu/api",
            headers=headers,
            params={"type": "eu", "from": f"{THIS_YEAR - YEARS_BACK}-01-01",
                    "to": date.today().isoformat(), "size": 300, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        js = r.json()
        rows += js["data"]
        last = int(js["last_page"])
        page += 1
    df = pd.DataFrame(rows)[["gasDayStart", "full"]]
    df.columns = ["date", "full_pct"]
    df["full_pct"] = pd.to_numeric(df["full_pct"], errors="coerce")
    df.sort_values("date").to_csv(CSV, index=False)  # keep a local copy
    return df


df = pd.read_csv(CSV) if "--offline" in sys.argv else download()
df["date"] = pd.to_datetime(df["date"])
df["year"] = df["date"].dt.year
df["doy"] = df["date"].dt.dayofyear

# 1) 5-year range for each day of the year
past = df[(df["year"] >= THIS_YEAR - YEARS_BACK) & (df["year"] < THIS_YEAR)]
band = past[past["doy"] <= 365].groupby("doy")["full_pct"].agg(["min", "max", "mean"])
current = df[df["year"] == THIS_YEAR].set_index("doy")["full_pct"]

# 2) Latest reading vs the 5-year average
last_doy = current.index.max()
last_date = df["date"].max().date()
level, avg = current[last_doy], band.loc[last_doy, "mean"]
print(f"EU gas storage on {last_date}: {level:.1f}% full")
print(f"5-year average for this date: {avg:.1f}%  "
      f"(range {band.loc[last_doy, 'min']:.1f}% - {band.loc[last_doy, 'max']:.1f}%)")
print(f"Gap vs average: {level - avg:+.1f} percentage points")

# 3) Simple projection: if the last 14 days' withdrawal pace continued
pace = (current[last_doy] - current[last_doy - 14]) / 14  # points per day
days_to_end_march = (pd.Timestamp(THIS_YEAR + 1, 3, 31) - pd.Timestamp(last_date)).days
print(f"Average change over the last 14 days: {pace:+.2f} pts/day")
print(f"Naive end-of-March level at that pace: {level + pace * days_to_end_march:.0f}% "
      "(withdrawals usually speed up in Dec-Feb, so this is an upper bound)")

# 4) Chart
fig, ax = plt.subplots(figsize=(10, 5))
ax.fill_between(band.index, band["min"], band["max"], color="#d9d9d9",
                label=f"{THIS_YEAR - YEARS_BACK}-{THIS_YEAR - 1} range")
ax.plot(band.index, band["mean"], "--", color="grey", label="5-year average")
ax.plot(current.index, current.values, color="#1f3864", lw=2.5, label=str(THIS_YEAR))
ax.annotate(f"{level:.0f}% ({level - avg:+.0f} pts vs avg)", (last_doy, level),
            xytext=(-60, -95), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#1f3864"), color="#1f3864")
months = pd.date_range(f"{THIS_YEAR}-01-01", periods=12, freq="MS")
ax.set_xticks(months.dayofyear, months.strftime("%b"))
ax.set(title=f"EU gas storage fill level - {THIS_YEAR} vs previous 5 years",
       ylabel="% full", ylim=(0, 100))
ax.text(0.99, 0.02, "Source: GIE AGSI+", transform=ax.transAxes, ha="right",
        fontsize=8, color="grey")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("eu_gas_storage.png", dpi=150)
print("Chart saved to eu_gas_storage.png")
