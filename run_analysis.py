"""Reproduces every number in the report. Run:  python run_analysis.py
Writes: data/daily_clean.csv, data/lifecycle.csv, data/song_day_stages.csv, data/flow.csv, outputs/results.json"""
import json, warnings
import numpy as np
import pandas as pd
from scipy import stats
from lifelines import CoxPHFitter
from lifelines.statistics import logrank_test
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.inspection import permutation_importance

from utils.pipeline import *
from utils.analytics import *

warnings.filterwarnings("ignore")
rng = np.random.default_rng(42)
R = {}


def js(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d")
    if isinstance(o, (np.bool_,)): return bool(o)
    return str(o)


def boot_ci(x, fn=np.mean, n=2000):
    x = np.asarray(x)
    b = [fn(rng.choice(x, len(x))) for _ in range(n)]
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def compare(a, b, name_a, name_b, col="total_days"):
    """Mann-Whitney + Cliff's delta + bootstrap CI of the mean ratio."""
    x, y = a[col].dropna().values, b[col].dropna().values
    u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    delta = 2 * u / (len(x) * len(y)) - 1
    ratio = lambda: np.mean(rng.choice(x, len(x))) / np.mean(rng.choice(y, len(y)))
    rr = [ratio() for _ in range(2000)]
    return {name_a: dict(n=len(x), mean=x.mean(), median=float(np.median(x))),
            name_b: dict(n=len(y), mean=y.mean(), median=float(np.median(y))),
            "mannwhitney_p": p, "cliffs_delta": delta, "mean_ratio": x.mean() / y.mean(),
            "mean_ratio_ci95": [float(np.percentile(rr, 2.5)), float(np.percentile(rr, 97.5))]}


# =============================================================== 1. validation + tables
df, rep = load_and_validate("data/Atlantic_Spain.csv")
R["validation"] = rep
life = build_lifecycle(df)
sd = classify_stages(df, life)
dom = dominant_stage(sd)
life["dominant_stage"] = life.song_id.map(dom).fillna("Unclassified")
flow = daily_flow(df)
R["n_songs"] = len(life)
R["left_censored"] = int(life.left_censored.sum()); R["right_censored"] = int(life.right_censored.sum())
R["reentry_songs"] = int(life.reentry.sum()); R["reentry_share"] = float(life.reentry.mean())

# first-run analysis (what matters for a fresh release)
d = df.sort_values(["song_id", "day_idx"]).copy()
d["run"] = d.groupby("song_id").day_idx.diff().ne(1).groupby(d.song_id).cumsum()
runs = d.groupby(["song_id", "run"]).agg(days=("date", "size"), start=("date", "min"), end=("date", "max")).reset_index()
R["runs_total"] = len(runs)
gaps = d.groupby("song_id").day_idx.diff()
R["reentry_gap_days_median"] = float(gaps[gaps > 1].median())
R["reentry_gap_le3_share"] = float((gaps[gaps > 1] <= 3).mean())
first_run = runs[runs.run == 1].set_index("song_id")
life["run1_days"] = life.song_id.map(first_run.days)

# save tables
sd_out = sd.merge(life[["song_id", "dominant_stage"]], on="song_id")
df.to_csv("data/daily_clean.csv", index=False)
life.to_csv("data/lifecycle.csv", index=False)
sd_out.to_csv("data/song_day_stages.csv", index=False)
flow.to_csv("data/flow.csv", index=False)

E = eligible(life)
R["eligible_songs"] = len(E)
R["eligible_completed"] = int(E.event_observed.sum())
R["total_days_desc"] = E.total_days.describe().to_dict()
R["survival_le3d_share"] = float((E.total_days <= 3).mean())
R["survival_le7d_share"] = float((E.total_days <= 7).mean())
R["survival_ge30d_share"] = float((E.total_days >= 30).mean())
R["survival_ge90d_share"] = float((E.total_days >= 90).mean())
R["reached_top10_share"] = float(E.reached_top10.mean())
R["reached_top1_share"] = float((E.peak_position == 1).mean())
R["time_to_peak_desc"] = E.time_to_peak.describe().to_dict()
R["time_to_peak_reached_first_week"] = float((E.time_to_peak <= 7).mean())
R["entry_position_desc"] = E.entry_position.describe().to_dict()
R["entry_pos_top10_share"] = float((E.entry_position <= 10).mean())
R["entry_pos_bottom10_share"] = float((E.entry_position > 40).mean())
kmf = km_fit(life)
R["km_median_all"] = float(kmf.median_survival_time_)
R["km_s30"] = float(kmf.predict(30)); R["km_s90"] = float(kmf.predict(90)); R["km_s7"] = float(kmf.predict(7))

# =============================================================== 2. stages
R["stage_share_songdays"] = sd.stage.value_counts(normalize=True).to_dict()
R["dominant_stage_counts"] = life.dominant_stage.value_counts().to_dict()
R["stage_transition"] = transition_matrix(sd).round(4).to_dict()
sens = []
for thr in [0.25, 0.5, 1.0]:
    for sdmax in [2.0, 3.0, 4.0]:
        s2 = classify_stages(df, life, slope_thr=thr, peak_max_std=sdmax)
        sh = s2.stage.value_counts(normalize=True)
        sens.append(dict(slope_thr=thr, peak_max_std=sdmax, **{k: float(sh.get(k, 0)) for k in STAGES}))
R["stage_sensitivity"] = sens
# time spent per stage per song (eligible songs)
stg_days = sd.groupby(["song_id", "stage"]).size().unstack(fill_value=0)
R["mean_days_per_stage"] = stg_days.loc[stg_days.index.isin(E.song_id)].mean().to_dict()

# =============================================================== 3. churn
f = flow[~flow.gap_before]
R["flow_days"] = len(f); R["flow_days_excluded_gap"] = int(flow.gap_before.sum())
R["entries_per_day_mean"] = float(f.entries.mean()); R["entries_per_day_median"] = float(f.entries.median())
R["churn_mean"] = float(f.churn_rate.mean()); R["churn_std"] = float(f.churn_rate.std()); R["churn_cv"] = float(f.churn_rate.std() / f.churn_rate.mean())
R["zero_entry_days_share"] = float((f.entries == 0).mean())
SHOCK = 8
shock = f[f.entries >= SHOCK]
R["shock_thr"] = SHOCK; R["shock_days"] = len(shock)
R["churn_excl_shocks"] = float(f[f.entries < SHOCK].churn_rate.mean())
R["entries_share_from_shocks"] = float(shock.entries.sum() / f.entries.sum())
# attribute shock days to artists
sh_rows = []
first_date = df.groupby("song_id").date.min()
for _, r in shock.iterrows():
    today = df[df.date == r.date]; yest = df[df.day_idx == r.day_idx - 1]
    new = today[~today.song_id.isin(yest.song_id)]
    top = new.artist_primary.value_counts()
    sh_rows.append(dict(date=r.date, entries=int(r.entries), top_artist=top.index[0], top_artist_entries=int(top.iloc[0]),
                        top10_new=int(r.top10_new), missing_pop=int(today.popularity_missing.sum())))
R["shock_days_detail"] = sh_rows
R["monthly_churn"] = f.groupby("month").churn_rate.mean().to_dict()
R["monthly_churn_excl_shocks"] = f[f.entries < SHOCK].groupby("month").churn_rate.mean().to_dict()
R["weekday_entries"] = f.groupby("weekday").entries.mean().to_dict()
R["weekday_entries_excl_shocks"] = f[f.entries < SHOCK].groupby("weekday").entries.mean().to_dict()
wk = [g.entries.values for _, g in f[f.entries < SHOCK].groupby("weekday")]
R["weekday_kruskal_p_excl_shocks"] = float(stats.kruskal(*wk).pvalue)
pc = position_churn(df)
R["position_churn_top10"] = float(pc.loc[1:10].mean()); R["position_churn_11_40"] = float(pc.loc[11:40].mean()); R["position_churn_bottom10"] = float(pc.loc[41:50].mean())
R["position_churn_by_rank"] = pc.to_dict()
R["top10_turnover_mean"] = float(f.top10_turnover.mean())
# Rank movement
mv = df.sort_values(["song_id", "day_idx"]).copy()
mv["move"] = mv.groupby("song_id").position.diff(); mv = mv[mv.groupby("song_id").day_idx.diff() == 1]
R["daily_rank_move_abs_mean"] = float(mv.move.abs().mean()); R["daily_rank_move_share_le2"] = float((mv.move.abs() <= 2).mean())
R["rank_move_by_position_bucket"] = {"1-10": float(mv[mv.position <= 10].move.abs().mean()), "41-50": float(mv[mv.position > 40].move.abs().mean())}
# same-artist concentration
art = df.groupby("artist_primary").size().sort_values(ascending=False)
p_ = art / art.sum()
R["artist_hhi"] = float((p_ ** 2).sum()); R["artist_top10_share"] = float(p_.head(10).sum()); R["artist_top1"] = [art.index[0], float(p_.iloc[0])]
R["n_primary_artists"] = int(art.size)
R["artist_top10"] = {k: float(v) for k, v in p_.head(10).items()}
per_day_art = df.groupby(["date", "artist_primary"]).size()
R["max_songs_one_artist_one_day"] = int(per_day_art.max())
R["days_with_artist_ge5"] = int((per_day_art.groupby("date").max() >= 5).sum())
R["mean_max_artist_songs_per_day"] = float(per_day_art.groupby("date").max().mean())

# =============================================================== 4. attributes vs lifecycle
R["counts_explicit"] = {"explicit": int(E.explicit.sum()), "clean": int((~E.explicit).sum())}
R["explicit_share_songs"] = float(life.explicit.mean()); R["explicit_share_songdays"] = float(df.is_explicit.mean())
R["cmp_explicit_all_eligible"] = compare(E[E.explicit], E[~E.explicit], "explicit", "clean")
comp = E[E.event_observed]
R["cmp_explicit_completed"] = compare(comp[comp.explicit], comp[~comp.explicit], "explicit", "clean")
R["cmp_explicit_peak"] = compare(E[E.explicit], E[~E.explicit], "explicit", "clean", col="peak_position")
R["cmp_explicit_ttp"] = compare(E[E.explicit], E[~E.explicit], "explicit", "clean", col="time_to_peak")
R["explicit_top10_rate"] = {"explicit": float(E[E.explicit].reached_top10.mean()), "clean": float(E[~E.explicit].reached_top10.mean())}
ct = pd.crosstab(E.explicit, E.reached_top10)
R["explicit_top10_chi2_p"] = float(stats.chi2_contingency(ct)[1])
R["cmp_single_all_eligible"] = compare(E[E.single], E[~E.single], "single", "album")
R["cmp_single_peak"] = compare(E[E.single], E[~E.single], "single", "album", col="peak_position")
R["cmp_single_ttp"] = compare(E[E.single], E[~E.single], "single", "album", col="time_to_peak")
R["cmp_single_entrypos"] = compare(E[E.single], E[~E.single], "single", "album", col="entry_position")
R["single_top10_rate"] = {"single": float(E[E.single].reached_top10.mean()), "album": float(E[~E.single].reached_top10.mean())}
R["single_share_songs"] = float(life.single.mean()); R["single_share_songdays"] = float((df.album_type == "single").mean())
lr = {}
for by in ["explicit", "single"]:
    a, b = [g for _, g in E.groupby(by)]
    lr[by] = float(logrank_test(a.total_days, b.total_days, a.event_observed, b.event_observed).p_value)
R["logrank_p"] = lr
R["km_median_by_explicit"] = {str(k): (float(km_fit(g).median_survival_time_)) for k, g in life.groupby("explicit")}
R["km_median_by_single"] = {str(k): (float(km_fit(g).median_survival_time_)) for k, g in life.groupby("single")}
R["km_s30_by_explicit"] = {str(k): float(km_fit(g).predict(30)) for k, g in life.groupby("explicit")}
R["km_s30_by_single"] = {str(k): float(km_fit(g).predict(30)) for k, g in life.groupby("single")}
E = E.assign(entry_bucket=pd.cut(E.entry_position, [0, 10, 25, 40, 50], labels=["1-10", "11-25", "26-40", "41-50"]))
R["km_s30_by_entry_bucket"] = {str(k): float(km_fit(g).predict(30)) for k, g in E.groupby("entry_bucket")}
R["km_median_by_entry_bucket"] = {str(k): float(km_fit(g).median_survival_time_) for k, g in E.groupby("entry_bucket")}
R["n_by_entry_bucket"] = E.entry_bucket.value_counts().to_dict()
# duration & album size
rho, p = stats.spearmanr(E.duration_min, E.total_days); R["spearman_duration_days"] = [float(rho), float(p)]
rho, p = stats.spearmanr(E.total_tracks, E.total_days); R["spearman_tracks_days"] = [float(rho), float(p)]
rho, p = stats.spearmanr(E.duration_min, E.peak_position); R["spearman_duration_peak"] = [float(rho), float(p)]
E = E.assign(dur_bin=pd.cut(E.duration_min, [0, 2.5, 3, 3.5, 4, 10], labels=["<2.5", "2.5-3", "3-3.5", "3.5-4", ">4"]))
R["duration_bins"] = E.groupby("dur_bin", observed=True).agg(n=("total_days", "size"), mean_days=("total_days", "mean"), median_days=("total_days", "median"), top10=("reached_top10", "mean")).round(3).to_dict("index")
E = E.assign(trk_bin=pd.cut(E.total_tracks, [0, 1, 3, 10, 20, 60], labels=["1", "2-3", "4-10", "11-20", "21+"]))
R["tracks_bins"] = E.groupby("trk_bin", observed=True).agg(n=("total_days", "size"), mean_days=("total_days", "mean"), median_days=("total_days", "median"), pos_std=("position_std", "mean"), top10=("reached_top10", "mean")).round(3).to_dict("index")
R["duration_median_min"] = float(life.duration_min.median())
R["reentry_by_type"] = {"single": float(E[E.single].reentry.mean()), "album": float(E[~E.single].reentry.mean())}
R["single_album_mix"] = {"single_songs": int(life.single.sum()), "album_songs": int((~life.single).sum())}
R["album_track_size_mean_in_chart"] = float(life[~life.single].total_tracks.mean())
# Album "drop dumps": how many album tracks entered on shock days
E2 = E.merge(pd.DataFrame(sh_rows)[["date"]].assign(shock=True), left_on="entry_date", right_on="date", how="left")
E2["shock"] = E2.shock.fillna(False).astype(bool)
R["shock_entrants"] = {"n": int(E2.shock.sum()), "mean_days_shock": float(E2[E2.shock].total_days.mean()), "mean_days_other": float(E2[~E2.shock].total_days.mean()),
                       "median_days_shock": float(E2[E2.shock].total_days.median()), "median_days_other": float(E2[~E2.shock].total_days.median()),
                       "top10_rate_shock": float(E2[E2.shock].reached_top10.mean()), "top10_rate_other": float(E2[~E2.shock].reached_top10.mean()),
                       "mannwhitney_p": float(stats.mannwhitneyu(E2[E2.shock].total_days, E2[~E2.shock].total_days).pvalue)}
R["shock_entrants"]["album_share_shock"] = float((~E2[E2.shock].single).mean()); R["shock_entrants"]["album_share_other"] = float((~E2[~E2.shock].single).mean())

# Cox PH
cx = E.copy()
first3 = df.sort_values(["song_id", "date"]).groupby("song_id").head(3).groupby("song_id").popularity.mean()
cx["entry_pop"] = cx.song_id.map(first3)
cx["log_tracks"] = np.log1p(cx.total_tracks)
cx = cx.assign(explicit_i=cx.explicit.astype(int), single_i=cx.single.astype(int),
               duration_z=(cx.duration_min - cx.duration_min.mean()) / cx.duration_min.std(),
               entry_pos_z=(cx.entry_position - cx.entry_position.mean()) / cx.entry_position.std())
cx["entry_pop_missing"] = cx.entry_pop.isna().astype(int)
cx["entry_pop_z"] = ((cx.entry_pop - cx.entry_pop.mean()) / cx.entry_pop.std()).fillna(0)
cph = CoxPHFitter(penalizer=0.01)
cols = ["total_days", "event_observed", "explicit_i", "single_i", "log_tracks", "duration_z", "entry_pos_z", "entry_pop_z", "entry_pop_missing"]
cph.fit(cx[cols].assign(event_observed=cx.event_observed.astype(int)), "total_days", "event_observed")
summ = cph.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]]
R["cox"] = summ.round(4).to_dict("index")
c2 = cx[["total_days", "event_observed", "explicit_i", "single_i", "log_tracks", "duration_z", "entry_pos_z"]].assign(event_observed=cx.event_observed.astype(int))
cph2 = CoxPHFitter(penalizer=0.01).fit(c2, "total_days", "event_observed")
R["cox_no_pop"] = cph2.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]].round(4).to_dict("index")
R["cox_no_pop_concordance"] = float(cph2.concordance_index_)
R["entry_pop_missing_share"] = float(cx.entry_pop_missing.mean())
R["entry_pop_missing_album_share"] = float((~cx[cx.entry_pop_missing == 1].single).mean())
R["entry_pop_missing_median_days"] = [float(cx[cx.entry_pop_missing == 1].total_days.median()), float(cx[cx.entry_pop_missing == 0].total_days.median())]
c3 = cx[cx.entry_pop_missing == 0][["total_days", "event_observed", "explicit_i", "single_i", "log_tracks", "duration_z", "entry_pos_z", "entry_pop_z"]].assign(event_observed=lambda x: x.event_observed.astype(int))
cph3 = CoxPHFitter(penalizer=0.01).fit(c3, "total_days", "event_observed")
R["cox_complete_pop"] = cph3.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]].round(4).to_dict("index")
R["cox_complete_pop_n"] = int(len(c3)); R["cox_concordance"] = float(cph.concordance_index_); R["cox_n"] = int(len(cx))

# OLS/Poisson-style regression on log days for completed songs (robustness)
import statsmodels.api as sm
X = sm.add_constant(cx[cx.event_observed][["explicit_i", "single_i", "log_tracks", "duration_z", "entry_pos_z"]].astype(float))
ols = sm.OLS(np.log(cx[cx.event_observed].total_days), X).fit(cov_type="HC3")
R["ols_logdays_completed"] = {k: dict(coef=float(ols.params[k]), p=float(ols.pvalues[k])) for k in X.columns}
R["ols_n"] = int(ols.nobs)

# =============================================================== 5. popularity vs lifecycle
sdp = sd.dropna(subset=["popularity"]).copy()
sdp = sdp.merge(life[["song_id", "left_censored"]], on="song_id")
nlc = sdp[~sdp.left_censored]
decay = nlc[nlc.chart_age <= 60].groupby("chart_age").popularity.agg(["mean", "count"])
decay = decay[decay["count"] >= 30]
R["pop_decay_by_age"] = {int(k): float(v) for k, v in decay["mean"].items() if k in (0, 1, 3, 7, 14, 21, 30, 45, 60)}
R["pop_mean_by_stage"] = sdp.groupby("stage").popularity.mean().to_dict()
sdp = sdp.sort_values(["song_id", "date"])
sdp["dpop"] = sdp.groupby("song_id").popularity.diff()
sdp["dpos"] = sdp.groupby("song_id").position.diff()
mvp = sdp[sdp.groupby("song_id").day_idx.diff() == 1]
R["pop_daily_change_by_stage"] = mvp.groupby("stage").dpop.mean().to_dict()
R["corr_pop_position"] = float(stats.spearmanr(sdp.popularity, sdp.position)[0])
# lead-lag: does today's popularity change precede rank change?
lead = {}
for lag in [-3, -2, -1, 0, 1, 2, 3]:
    tmp = sdp.copy()
    tmp["dpos_shift"] = tmp.groupby("song_id").dpos.shift(-lag)  # lag>0: rank change happens after popularity change
    t = tmp.dropna(subset=["dpop", "dpos_shift"])
    lead[lag] = float(stats.spearmanr(t.dpop, t.dpos_shift)[0])
R["leadlag_dpop_vs_dpos"] = lead
Ep = E.dropna(subset=["days_to_popularity_peak"])
R["pop_peak_vs_rank_peak"] = dict(median_days_pop_peak=float(Ep.days_to_popularity_peak.median()), median_days_rank_peak=float(Ep.time_to_peak.median()),
                                  spearman=float(stats.spearmanr(Ep.days_to_popularity_peak, Ep.time_to_peak)[0]),
                                  pop_peak_before_rank_peak_share=float((Ep.days_to_popularity_peak < Ep.time_to_peak).mean()),
                                  same_day_share=float((Ep.days_to_popularity_peak == Ep.time_to_peak).mean()))
R["peak_pop_desc"] = E.peak_popularity.describe().to_dict()
R["spearman_peakpop_days"] = [float(x) for x in stats.spearmanr(E.peak_popularity.fillna(E.peak_popularity.median()), E.total_days)]
R["spearman_entrypop_days"] = [float(x) for x in stats.spearmanr(cx.entry_pop.fillna(cx.entry_pop.median()), cx.total_days)]
R["share_enter_at_best_position"] = float((E.time_to_peak == 0).mean())
R["ttp_among_top10_reachers"] = E[E.reached_top10].time_to_peak.describe().to_dict()
cmpl = E[E.event_observed & E.peak_popularity.notna() & E.popularity_at_exit.notna()]
R["pop_peak_minus_exit_mean"] = float((cmpl.peak_popularity - cmpl.popularity_at_exit).mean())
# popularity relative to exit day (completed songs, >=15 days on chart)
cc = nlc.merge(life[["song_id", "event_observed", "total_days"]], on="song_id")
cc = cc[cc.event_observed & (cc.total_days >= 15)]
cc["days_to_exit"] = cc.groupby("song_id").cumcount(ascending=False)
R["pop_by_days_to_exit"] = {int(k): float(v) for k, v in cc[cc.days_to_exit.isin([0, 3, 7, 14])].groupby("days_to_exit").popularity.mean().items()}
R["pop_by_days_to_exit_pos"] = {int(k): float(v) for k, v in cc[cc.days_to_exit.isin([0, 3, 7, 14])].groupby("days_to_exit").position.mean().items()}

# =============================================================== 6. early-warning model (first 7 chart days)
f7 = d.merge(life[["song_id", "left_censored", "entry_date", "exit_date", "right_censored", "total_days", "peak_position", "explicit", "single", "total_tracks", "duration_min"]], on="song_id")
f7 = f7[~f7.left_censored]
f7["age"] = f7.groupby("song_id").cumcount()
w = f7[f7.age < 7]
feat = w.groupby("song_id").agg(entry_position=("position", "first"), mean_pos7=("position", "mean"), best_pos7=("position", "min"),
                                 pos_std7=("position", "std"), days_in7=("position", "size"), mean_pop7=("popularity", "mean"),
                                 top10_days7=("position", lambda s: (s <= 10).sum()))
feat["slope7"] = w.groupby("song_id").apply(lambda g: np.polyfit(np.arange(len(g)), g.position, 1)[0] if len(g) >= 3 else np.nan)
feat = feat.join(life.set_index("song_id")[["explicit", "single", "total_tracks", "duration_min", "entry_date", "exit_date", "right_censored", "total_days", "peak_position"]])
feat = feat[feat.days_in7 >= 3]   # require >=3 chart days so a window exists
last = df.date.max()
feat["can_observe30"] = (feat.entry_date + pd.Timedelta(days=30) <= last)
mdl = feat[feat.can_observe30].copy()
mdl["y_survive30"] = (mdl.total_days >= 30).astype(int)
mdl["y_top10"] = (mdl.peak_position <= 10).astype(int)
mdl["explicit"] = mdl.explicit.astype(int); mdl["single"] = mdl.single.astype(int)
X_cols = ["entry_position", "mean_pos7", "best_pos7", "pos_std7", "slope7", "mean_pop7", "explicit", "single", "total_tracks", "duration_min", "days_in7"]
cut = mdl.entry_date.quantile(0.7)
tr, te = mdl[mdl.entry_date <= cut], mdl[mdl.entry_date > cut]
med = tr[X_cols].median()
early = {"n_train": len(tr), "n_test": len(te), "cutoff": cut, "n_songs_with_3days": len(feat)}
for tgt in ["y_survive30", "y_top10"]:
    if te[tgt].nunique() < 2 or tr[tgt].nunique() < 2:
        continue
    lg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.5)).fit(tr[X_cols].fillna(med), tr[tgt])
    gb = GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=1).fit(tr[X_cols].fillna(med), tr[tgt])
    base = -te.mean_pos7  # naive baseline: average position in first week
    early[tgt] = dict(base_rate_test=float(te[tgt].mean()), auc_logit=float(roc_auc_score(te[tgt], lg.predict_proba(te[X_cols].fillna(med))[:, 1])),
                      auc_gb=float(roc_auc_score(te[tgt], gb.predict_proba(te[X_cols].fillna(med))[:, 1])), auc_baseline_mean_pos7=float(roc_auc_score(te[tgt], base)))
    pi = permutation_importance(gb, te[X_cols].fillna(med), te[tgt], scoring="roc_auc", n_repeats=15, random_state=1)
    early[tgt]["importance"] = dict(sorted({c: float(v) for c, v in zip(X_cols, pi.importances_mean)}.items(), key=lambda kv: -kv[1]))
    if tgt == "y_survive30":
        mdl["score_survive30"] = np.nan
        mdl.loc[:, "score_survive30"] = gb.predict_proba(mdl[X_cols].fillna(med))[:, 1]
        mdl["split"] = np.where(mdl.entry_date <= cut, "train", "test")
R["early_warning"] = early
mdl.reset_index()[["song_id", "score_survive30", "split", "y_survive30", "y_top10"]].to_csv("data/early_warning_scores.csv", index=False)

# =============================================================== 7. clusters (lifecycle archetypes)
cl = E[E.total_days >= 3].copy()
cl["log_days"] = np.log(cl.total_days); cl["ttp_frac"] = cl.time_to_peak / cl.span_days.clip(lower=1)
cl["top10_frac"] = cl.days_top10 / cl.total_days
cl["pos_std"] = cl.position_std.fillna(0)
cf = ["log_days", "peak_position", "ttp_frac", "top10_frac", "pos_std", "entry_position"]
Z = StandardScaler().fit_transform(cl[cf])
sil = {}
for k in [3, 4, 5, 6]:
    sil[k] = float(silhouette_score(Z, KMeans(k, n_init=10, random_state=1).fit_predict(Z)))
R["cluster_silhouette"] = sil
K = 4
cl["cluster"] = KMeans(K, n_init=20, random_state=1).fit_predict(Z)
prof = cl.groupby("cluster").agg(n=("song_id", "size"), mean_days=("total_days", "mean"), median_days=("total_days", "median"), peak=("peak_position", "median"),
                                 entry_pos=("entry_position", "median"), ttp=("time_to_peak", "median"), top10_frac=("top10_frac", "mean"),
                                 pos_std=("pos_std", "mean"), explicit=("explicit", "mean"), single=("single", "mean"),
                                 right_cens=("right_censored", "mean"), reentry=("reentry", "mean"))
# name archetypes from the profile (rank-based rules, not hard-coded cluster ids)
names = {}
by_days = prof.mean_days.sort_values(ascending=False).index.tolist()
names[by_days[0]] = "Evergreen Hit"
names[by_days[1]] = "Slow Burner"
lo = prof.loc[by_days[2:]].peak.sort_values().index.tolist()
names[lo[0]] = "Debut-and-Fade"
for c in lo[1:]:
    names[c] = "Bottom-Chart Filler"
prof["archetype"] = prof.index.map(names)
R["clusters"] = prof.round(3).reset_index().to_dict("records")
cl["archetype"] = cl.cluster.map(names)
cl[["song_id", "cluster", "archetype"]].to_csv("data/archetypes.csv", index=False)

# =============================================================== 8. KPIs (overall + segments)
R["kpis_all"] = compute_kpis(sd, life, flow)
for nm, m_sd, m_life in [("explicit", sd.is_explicit, life.explicit), ("clean", ~sd.is_explicit, ~life.explicit),
                         ("single", sd.album_type == "single", life.single), ("album", sd.album_type == "album", ~life.single)]:
    sub = sd[m_sd]
    R["kpis_" + nm] = compute_kpis(sub, life[m_life], daily_flow(sub))

# freshness by month (after burn-in)
x = sd[sd.date >= sd.date.min() + pd.Timedelta(days=BURN_IN_DAYS)].copy()
x["m"] = x.date.dt.to_period("M").astype(str)
R["freshness_by_month"] = x.groupby("m").apply(lambda g: (g.chart_age <= 30).mean()).to_dict()
R["catalog_by_month"] = x.groupby("m").apply(lambda g: (g.chart_age > 90).mean()).to_dict()
R["age_mix_overall"] = dict(le7=float((x.chart_age <= 7).mean()), le30=float((x.chart_age <= 30).mean()), gt90=float((x.chart_age > 90).mean()))
R["avg_chart_age_top10"] = float(x[x.position <= 10].chart_age.mean()); R["avg_chart_age_bottom10"] = float(x[x.position > 40].chart_age.mean())
R["top1_holders"] = int(df[df.position == 1].song_id.nunique())
top1_days = df[df.position == 1].groupby("song_id").size().sort_values(ascending=False)
R["top1_most_days"] = {life.set_index("song_id").label[k]: int(v) for k, v in top1_days.head(5).items()}
longest = life.sort_values("total_days", ascending=False).head(8)
R["longest_songs"] = longest[["label", "total_days", "peak_position", "left_censored", "right_censored"]].to_dict("records")
R["most_explicit_top10_periods"] = None

def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)) and not np.isfinite(o): return None
    return o


json.dump(clean(R), open("outputs/results.json", "w"), default=js, indent=1)
print("done; keys:", len(R))
