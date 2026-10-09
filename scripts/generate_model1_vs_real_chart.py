"""Renders the 12-race Model 1 vs real-time line chart (10 races Model 1 beat the
real winner's time, plus the 2 closest races where it didn't) from
model1_vs_real_12races.csv, saved as a PNG for the repo."""
import csv
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader((HERE / "model1_vs_real_12races.csv").open(encoding="utf-8")))

labels = [f"{r['year']}\n{r['race']}" for r in rows]
real = [float(r["real_time_seconds"]) for r in rows]
m1 = [float(r["m1_race_time_seconds"]) for r in rows]
x = list(range(len(rows)))
boundary = sum(1 for r in rows if r["group"] == "m1_faster")

fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(x, real, marker="o", color="#2a78d6", linewidth=2, label="Real winner's time")
ax.plot(x, m1, marker="o", color="#eb6834", linewidth=2, label="Model 1 predicted time")
ax.axvline(boundary - 0.5, color="#898781", linestyle="--", linewidth=1)

for i, r in enumerate(rows):
    delta = float(r["m1_delta_vs_real_seconds"])
    y = min(real[i], m1[i]) - 25
    color = "#0ca30c" if delta < 0 else "#d03b3b"
    ax.text(i, y, f"{delta:+.1f}s", ha="center", fontsize=9, fontweight="bold", color=color)

ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)
ax.set_ylabel("Race time (seconds)")
ax.set_title("Model 1 vs Real Race Time — 10 races Model 1 beat + 2 closest otherwise")
ax.legend(loc="upper left")
ax.grid(axis="y", linestyle="-", alpha=0.3)
fig.tight_layout()

out_path = HERE / "model1_vs_real_12races.png"
fig.savefig(out_path, dpi=1200)
print(f"Saved {out_path}")
