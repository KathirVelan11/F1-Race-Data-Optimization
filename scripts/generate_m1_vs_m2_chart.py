"""Plots Model 1 (fastest strategy) vs Model 2 (balanced strategy) predicted race time
for all races in validation_random_results.csv. Model 2 rows whose solve hit the time
limit are drawn as hollow markers because their incumbent can violate the minimum
pit-stop rule."""
import csv
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader((HERE / "validation_random_results.csv").open(encoding="utf-8")))

labels = [f"{r['year']} {r['race'].replace(' Grand Prix', '')}" for r in rows]
m1 = [float(r["m1_race_time_seconds"]) for r in rows]
m2 = [float(r["m2_balanced_time_seconds"]) for r in rows]
gap = [b - a for a, b in zip(m1, m2)]
timed_out = ["time limit" in r["m2_status"] for r in rows]
x = list(range(len(rows)))
hollow = [i for i, t in enumerate(timed_out) if t]
solid = [i for i, t in enumerate(timed_out) if not t]

fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(22, 11), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
)

ax.plot(x, m1, color="#2a78d6", linewidth=1.5, label="Model 1 - fastest strategy")
ax.plot(x, m2, color="#eb6834", linewidth=1.5, label="Model 2 - balanced strategy")
ax.scatter([x[i] for i in solid], [m1[i] for i in solid], color="#2a78d6", s=18, zorder=3)
ax.scatter([x[i] for i in solid], [m2[i] for i in solid], color="#eb6834", s=18, zorder=3)
ax.scatter([x[i] for i in hollow], [m2[i] for i in hollow], facecolors="white",
           edgecolors="#eb6834", s=40, linewidths=1.5, zorder=4)
ax.set_ylabel("Predicted race time (seconds)")
ax.set_title("Fastest (Model 1) vs balanced (Model 2) strategy - all 109 races")
ax.legend(loc="upper left")
ax.grid(axis="y", linestyle="-", alpha=0.3)

colors = ["#898781" if t else "#2a78d6" for t in timed_out]
ax2.bar(x, gap, color=colors, width=0.8)
ax2.axhline(0, color="#52514e", linewidth=0.8)
ax2.set_ylabel("Model 2 - Model 1 (s)")
ax2.grid(axis="y", linestyle="-", alpha=0.3)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=90, ha="center", fontsize=6)
ax2.set_xlim(-1, len(rows))

fig.tight_layout()
out_path = HERE / "m1_vs_m2_109races.jpg"
fig.savefig(out_path, dpi=1200)
print(f"Saved {out_path}")
