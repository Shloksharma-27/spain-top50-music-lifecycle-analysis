"""Static figures for the research paper. Run after run_analysis.py."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from utils.pipeline import STAGES
from utils.analytics import km_curve, eligible

OI = dict(blue="#0072B2", orange="#E69F00", green="#009E73", verm="#D55E00", sky="#56B4E9", pink="#CC79A7", yellow="#F0E442", grey="#7f7f7f")
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": .25,
                     "figure.dpi": 150, "savefig.bbox": "tight", "axes.titleweight": "bold"})
OUT = "outputs/figures/"
R = json.load(open("outputs/results.json"))
life = pd.read_csv("data/lifecycle.csv", parse_dates=["entry_date", "exit_date", "peak_date"])
sd = pd.read_csv("data/song_day_stages.csv", parse_dates=["date"])
flow = pd.read_csv("data/flow.csv", parse_dates=["date"])
arch = pd.read_csv("data/archetypes.csv")
E = eligible(life)

# 1 daily entries
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.bar(flow.date, flow.entries, width=1, color=OI["sky"], label="New songs per day")
sh = flow[flow.entries >= R["shock_thr"]]
ax.bar(sh.date, sh.entries, width=1.6, color=OI["verm"], label=f"Shock days (>= {R['shock_thr']} entries)")
ax.plot(flow.date, flow.churn_7d * 50, color="black", lw=1.4, label="7-day average")
ax.set_ylabel("Songs entering Top 50"); ax.set_title("Daily playlist entries: quiet baseline punctuated by album-drop shocks"); ax.legend(frameon=False, ncol=3, loc="upper left")
fig.savefig(OUT + "fig01_daily_entries.png"); plt.close()

# 2 KM survival
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for ax, by, lab, cols in [(axs[0], "single", {True: "Single", False: "Album track"}, {True: OI["blue"], False: OI["orange"]}),
                          (axs[1], "explicit", {True: "Explicit", False: "Clean"}, {True: OI["verm"], False: OI["green"]})]:
    for g, sub in life.groupby(by):
        k = km_curve(sub, max_days=120)
        ax.step(k.t, k.survival, where="post", color=cols[g], label=f"{lab[g]} (n={k.n.iloc[0]})")
        ax.fill_between(k.t, k.lo, k.hi, step="post", color=cols[g], alpha=.15)
    ax.set_xlabel("Days since chart entry"); ax.legend(frameon=False)
axs[0].set_ylabel("Share still on Top 50"); axs[0].set_title(f"Single vs album track (log-rank p={R['logrank_p']['single']:.4f})")
axs[1].set_title(f"Explicit vs clean (log-rank p={R['logrank_p']['explicit']:.2f})")
fig.savefig(OUT + "fig02_km_survival.png"); plt.close()

# 3 stage distribution + transition
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [1, 1.1]})
stg = [s for s in STAGES if s != "Unclassified"]
sh_ = pd.Series(R["stage_share_songdays"]).reindex(stg)
cmap = {"New Entry": OI["sky"], "Growth": OI["green"], "Peak": OI["blue"], "Mature": OI["grey"], "Decline": OI["verm"]}
axs[0].barh(stg[::-1], sh_[::-1] * 100, color=[cmap[s] for s in stg[::-1]])
for i, v in enumerate(sh_[::-1] * 100): axs[0].text(v + .5, i, f"{v:.0f}%", va="center")
axs[0].set_xlabel("% of song-days"); axs[0].set_title("Lifecycle stage mix"); axs[0].grid(False)
T = pd.DataFrame(R["stage_transition"]).reindex(index=stg, columns=stg)
im = axs[1].imshow(T.values, cmap="Blues", vmin=0, vmax=1)
axs[1].set_xticks(range(5)); axs[1].set_xticklabels(stg, rotation=35, ha="right"); axs[1].set_yticks(range(5)); axs[1].set_yticklabels(stg)
for i in range(5):
    for j in range(5): axs[1].text(j, i, f"{T.values[i, j]:.2f}", ha="center", va="center", color="white" if T.values[i, j] > .5 else "black", fontsize=8)
axs[1].set_title("Next-day stage transition"); axs[1].grid(False); axs[1].set_xlabel("Tomorrow"); axs[1].set_ylabel("Today")
fig.savefig(OUT + "fig03_stages.png"); plt.close()

# 4 churn by month & weekday
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [2, 1]})
m = pd.DataFrame({"all": R["monthly_churn"], "excl": R["monthly_churn_excl_shocks"]}) * 100
x = np.arange(len(m)); axs[0].bar(x - .2, m["all"], .4, color=OI["orange"], label="All days"); axs[0].bar(x + .2, m.excl, .4, color=OI["blue"], label="Excluding shock days")
axs[0].set_xticks(x); axs[0].set_xticklabels(m.index, rotation=60, ha="right", fontsize=8); axs[0].set_ylabel("Daily churn (% of 50 slots)"); axs[0].legend(frameon=False); axs[0].set_title("Churn by month")
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
w = pd.Series(R["weekday_entries_excl_shocks"]).reindex(days)
axs[1].bar([d[:3] for d in days], w, color=[OI["verm"] if d in ("Monday", "Tuesday") else OI["sky"] for d in days])
axs[1].set_ylabel("Avg new songs / day"); axs[1].set_title("By weekday (excl. shocks)")
fig.savefig(OUT + "fig04_churn_month_weekday.png"); plt.close()

# 5 churn by rank
pc = pd.Series(R["position_churn_by_rank"]); pc.index = pc.index.astype(int)
fig, ax = plt.subplots(figsize=(8, 3.2))
ax.bar(pc.index, pc.values * 100, color=[OI["blue"] if i <= 10 else OI["grey"] if i <= 40 else OI["verm"] for i in pc.index])
ax.set_xlabel("Chart position"); ax.set_ylabel("% of days occupant changes"); ax.set_title("Rank-level turnover: the top is sticky, the bottom is a revolving door")
fig.savefig(OUT + "fig05_position_churn.png"); plt.close()

# 6 popularity vs rank timing
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
dec = pd.Series(R["pop_decay_by_age"]); dec.index = dec.index.astype(int)
axs[0].plot(dec.index, dec.values, marker="o", color=OI["blue"]); axs[0].set_xlabel("Days since chart entry"); axs[0].set_ylabel("Mean popularity score")
axs[0].set_title("Popularity ramps after entry")
d2 = pd.Series(R["pop_by_days_to_exit"]); d2.index = d2.index.astype(int); d3 = pd.Series(R["pop_by_days_to_exit_pos"]); d3.index = d3.index.astype(int)
ax2 = axs[1]; ax2.plot(d2.index, d2.values, marker="o", color=OI["blue"], label="Popularity (left)"); ax2.set_ylim(70, 85)
ax3 = ax2.twinx(); ax3.plot(d3.index, d3.values, marker="s", color=OI["verm"], label="Chart position (right)"); ax3.invert_yaxis(); ax3.spines["right"].set_visible(True); ax3.grid(False)
ax2.invert_xaxis(); ax2.set_xlabel("Days before final exit"); ax2.set_ylabel("Popularity"); ax3.set_ylabel("Position (lower = better)")
ax2.set_title("Rank slides, popularity stays flat")
fig.savefig(OUT + "fig06_popularity.png"); plt.close()

# 7 duration + album size
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
tb = pd.DataFrame(R["tracks_bins"]).T; db = pd.DataFrame(R["duration_bins"]).T
axs[0].bar(tb.index, tb.median_days, color=OI["orange"]); axs[0].set_xlabel("Tracks on the release"); axs[0].set_ylabel("Median days on chart"); axs[0].set_title("Album size vs longevity")
for i, (n, v) in enumerate(zip(tb.n, tb.median_days)): axs[0].text(i, v + .5, f"n={int(n)}", ha="center", fontsize=8)
axs[1].bar(db.index, db.median_days, color=OI["sky"]); axs[1].set_xlabel("Song length (min)"); axs[1].set_title("Song length vs longevity")
for i, (n, v) in enumerate(zip(db.n, db.median_days)): axs[1].text(i, v + .3, f"n={int(n)}", ha="center", fontsize=8)
fig.savefig(OUT + "fig07_size_duration.png"); plt.close()

# 8 archetypes
cl = E.merge(arch, on="song_id")
fig, ax = plt.subplots(figsize=(7.5, 4.6))
cc = {"Evergreen Hit": OI["blue"], "Slow Burner": OI["green"], "Debut-and-Fade": OI["orange"], "Bottom-Chart Filler": OI["grey"]}
for a, g in cl.groupby("archetype"): ax.scatter(g.total_days, g.peak_position, s=18, alpha=.6, color=cc[a], label=f"{a} (n={len(g)})")
ax.set_xscale("log"); ax.invert_yaxis(); ax.set_xlabel("Days on chart (log)"); ax.set_ylabel("Peak position"); ax.legend(frameon=False, fontsize=8); ax.set_title("Lifecycle archetypes")
fig.savefig(OUT + "fig08_archetypes.png"); plt.close()

# 9 lifespan histogram
fig, ax = plt.subplots(figsize=(8, 3.4))
bins = np.unique(np.round(np.logspace(0, np.log10(E.total_days.max()), 30)))
ax.hist(E.total_days, bins=bins, color=OI["blue"], alpha=.85); ax.set_xscale("log")
for v, lab in [(3, "3d"), (7, "7d"), (30, "30d"), (90, "90d")]: ax.axvline(v, color=OI["verm"], ls="--", lw=1); ax.text(v * 1.03, ax.get_ylim()[1] * .92, lab, color=OI["verm"])
ax.set_xlabel("Total days on Top 50 (log scale)"); ax.set_ylabel("Songs"); ax.set_title("Most songs are short-lived; a minority becomes catalog")
fig.savefig(OUT + "fig09_lifespan.png"); plt.close()

# 10 shock vs other survival
shock_dates = {pd.Timestamp(r["date"]) for r in R["shock_days_detail"]}
lf = life.assign(shock=life.entry_date.isin(shock_dates))
fig, ax = plt.subplots(figsize=(6.5, 3.8))
for g, sub in lf.groupby("shock"):
    k = km_curve(sub, max_days=120); lab = "Entered on a shock day" if g else "Entered on a normal day"
    ax.step(k.t, k.survival, where="post", color=OI["verm"] if g else OI["blue"], label=f"{lab} (n={k.n.iloc[0]})")
ax.set_xlabel("Days since chart entry"); ax.set_ylabel("Share still on Top 50"); ax.legend(frameon=False); ax.set_title("Album-drop entrants exit far faster")
fig.savefig(OUT + "fig10_shock_survival.png"); plt.close()

# 11 freshness
fm = pd.DataFrame({"Fresh (<=30 chart-days)": R["freshness_by_month"], "Catalog (>90 chart-days)": R["catalog_by_month"]}) * 100
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.plot(fm.index, fm.iloc[:, 0], marker="o", color=OI["orange"], label=fm.columns[0]); ax.plot(fm.index, fm.iloc[:, 1], marker="s", color=OI["blue"], label=fm.columns[1])
ax.set_ylabel("% of chart slots"); ax.set_xticks(range(len(fm))); ax.set_xticklabels(fm.index, rotation=60, ha="right", fontsize=8); ax.legend(frameon=False); ax.set_title("Fresh vs catalog share of the chart")
fig.savefig(OUT + "fig11_freshness.png"); plt.close()

# 12 example trajectories
ex = {"Evergreen Hit": "columbia | quevedo", "Slow Burner": None, "Debut-and-Fade": None, "Bottom-Chart Filler": None}
fig, ax = plt.subplots(figsize=(9, 3.8))
for a, colr in cc.items():
    pool = cl[(cl.archetype == a) & (~cl.right_censored)].sort_values("total_days")
    if pool.empty: continue
    pick = pool.iloc[len(pool) // 2] if a != "Evergreen Hit" else pool.iloc[-3]
    s = sd[sd.song_id == pick.song_id]
    ax.plot(s.chart_age, s.position, color=colr, lw=1.6, label=f"{a}: {pick.label[:32]}")
ax.set_xlim(0, 200); ax.invert_yaxis(); ax.set_xlabel("Chart days since entry"); ax.set_ylabel("Position"); ax.legend(frameon=False, fontsize=8); ax.set_title("Illustrative rank trajectories per archetype")
fig.savefig(OUT + "fig12_trajectories.png"); plt.close()
print("figures ok")
