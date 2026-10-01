"""Data validation, normalization, lifecycle construction, stage classification and churn.
All functions are pure (DataFrame in -> DataFrame out) so the Streamlit app can reuse them."""
import re
import unicodedata
import numpy as np
import pandas as pd

STAGES = ["New Entry", "Growth", "Peak", "Mature", "Decline", "Unclassified"]
DEFAULT_PARAMS = dict(new_days=7, slope_thr=0.5, peak_max_pos=10, peak_max_std=3.0, window=7, min_obs=4)


# ----------------------------------------------------------------------------- normalization
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


_FEAT = re.compile(r"\s*[\(\[]\s*(feat\.?|ft\.?|with|con)\s[^\)\]]*[\)\]]", re.I)
_FEAT_DASH = re.compile(r"\s*-\s*(feat\.?|ft\.?|con)\s.*$", re.I)


def norm_title(t: str) -> str:
    t = _FEAT_DASH.sub("", _FEAT.sub("", str(t)))
    t = strip_accents(t).lower()
    t = re.sub(r"\s*-\s*(remastered.*|\d{4} remaster.*)$", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def primary_artist(a: str) -> str:
    first = re.split(r"\s*(?:&|,| feat\.? | ft\.? )\s*", str(a), maxsplit=1)[0]
    return re.sub(r"\s+", " ", strip_accents(first).lower()).strip()


# ----------------------------------------------------------------------------- validation
def load_and_validate(path: str):
    """Returns (clean_daily_df, validation_report dict)."""
    raw = pd.read_csv(path)
    rep = {"raw_rows": len(raw), "raw_cols": list(raw.columns), "nulls": int(raw.isna().sum().sum())}
    raw["date"] = pd.to_datetime(raw["date"], format="%d-%m-%Y")
    raw["_order"] = np.arange(len(raw))
    rep["date_min"], rep["date_max"] = raw.date.min(), raw.date.max()
    rep["calendar_days"] = (raw.date.max() - raw.date.min()).days + 1
    cnt = raw.groupby("date").size()
    rep["observed_days"] = len(cnt)
    full = pd.date_range(raw.date.min(), raw.date.max())
    rep["missing_dates"] = [d.strftime("%Y-%m-%d") for d in full.difference(cnt.index)]
    rep["days_not_50"] = {d.strftime("%Y-%m-%d"): int(n) for d, n in cnt[cnt != 50].items()}
    rep["exact_duplicate_rows"] = int(raw.drop(columns="_order").duplicated().sum())
    rep["dup_date_position"] = int(raw.duplicated(["date", "position"]).sum())

    # Treatment 1: a day with two full 50-row snapshots -> keep the first snapshot (file order)
    df = raw.copy()
    df["_rank_in_pos"] = df.groupby(["date", "position"]).cumcount()
    rep["double_snapshot_rows_dropped"] = int((df._rank_in_pos > 0).sum())
    df = df[df._rank_in_pos == 0].drop(columns="_rank_in_pos")

    # Treatment 2: popularity==0 is an API failure -> set NaN, flagged
    df["popularity_missing"] = df.popularity.eq(0)
    rep["zero_popularity_rows"] = int(df.popularity_missing.sum())
    df.loc[df.popularity_missing, "popularity"] = np.nan

    # Normalization
    df["title_norm"] = df.song.map(norm_title)
    df["artist_primary"] = df.artist.map(primary_artist)
    df["song_id"] = df.title_norm + " | " + df.artist_primary
    df["label"] = df.song.str.strip() + " — " + df.artist.str.split(r"\s*&\s*", regex=True).str[0].str.strip()
    rep["distinct_raw_song_artist"] = int(df.groupby(["song", "artist"]).ngroups)
    rep["distinct_song_ids"] = int(df.song_id.nunique())

    # Treatment 3: same song_id twice in a day -> keep best (lowest) position
    df = df.sort_values(["date", "position", "_order"])
    dup = df.duplicated(["date", "song_id"], keep="first")
    rep["same_song_twice_same_day_dropped"] = int(dup.sum())
    df = df[~dup]

    days = np.sort(df.date.unique())
    df["day_idx"] = df.date.map({d: i for i, d in enumerate(days)})
    cal = pd.Series(pd.to_datetime(days))
    gap = cal.diff().dt.days.fillna(1).gt(1)
    df["gap_before_day"] = df.day_idx.map(dict(enumerate(gap.values)))
    rep["final_rows"] = len(df)
    rep["final_days"] = int(df.date.nunique())
    rep["rows_per_day_min"] = int(df.groupby("date").size().min())
    rep["rows_per_day_max"] = int(df.groupby("date").size().max())
    return df.drop(columns=["_order"]).reset_index(drop=True), rep


# ----------------------------------------------------------------------------- lifecycle
def _mode(s):
    m = s.mode()
    return m.iloc[0] if len(m) else s.iloc[0]


def build_lifecycle(df: pd.DataFrame) -> pd.DataFrame:
    first_date, last_date = df.date.min(), df.date.max()
    df = df.sort_values(["song_id", "date"])
    new_run = df.groupby("song_id").day_idx.diff().ne(1)  # consecutive observed days => same run
    df = df.assign(run=new_run.groupby(df.song_id).cumsum())
    g = df.groupby("song_id")
    life = g.agg(
        label=("label", "first"), song=("song", "first"), artist=("artist", "first"), artist_primary=("artist_primary", "first"),
        entry_date=("date", "min"), exit_date=("date", "max"), total_days=("date", "size"),
        number_of_runs=("run", "max"), peak_position=("position", "min"), avg_position=("position", "mean"),
        position_std=("position", "std"), peak_popularity=("popularity", "max"), avg_popularity=("popularity", "mean"),
        is_explicit=("is_explicit", _mode), album_type=("album_type", _mode), total_tracks=("total_tracks", _mode),
        duration_ms=("duration_ms", "median"),
        album_cover_url=("album_cover_url", "first") if "album_cover_url" in df.columns else ("song", lambda _: ""),
        days_top10=("position", lambda s: int((s <= 10).sum())), days_top25=("position", lambda s: int((s <= 25).sum())),
    )
    life["span_days"] = (life.exit_date - life.entry_date).dt.days + 1
    life["duration_min"] = life.duration_ms / 60000
    srt = df.sort_values(["song_id", "date"])
    first_rows = srt.drop_duplicates("song_id", keep="first").set_index("song_id")
    last_rows = srt.drop_duplicates("song_id", keep="last").set_index("song_id")
    life["entry_position"] = first_rows.position
    life["exit_position"] = last_rows.position
    life["popularity_at_entry"] = first_rows.popularity
    life["popularity_at_exit"] = last_rows.popularity
    pk = df.sort_values(["song_id", "position", "date"]).drop_duplicates("song_id").set_index("song_id")
    life["peak_date"] = pk.date
    life["time_to_peak"] = (life.peak_date - life.entry_date).dt.days
    pp = df.dropna(subset=["popularity"]).sort_values(["song_id", "popularity", "date"], ascending=[True, False, True]).drop_duplicates("song_id").set_index("song_id")
    life["popularity_peak_date"] = pp.date
    life["days_to_popularity_peak"] = (life.popularity_peak_date - life.entry_date).dt.days
    life["left_censored"] = life.entry_date.eq(first_date)
    life["right_censored"] = life.exit_date.eq(last_date)
    life["event_observed"] = ~life.right_censored
    life["reentry"] = life.number_of_runs > 1
    life["reached_top10"] = life.peak_position <= 10
    life["single"] = life.album_type.eq("single")
    life["explicit"] = life.is_explicit.astype(bool)
    return life.reset_index()


# ----------------------------------------------------------------------------- stages
def _roll_slope(pos: np.ndarray, window: int, min_obs: int):
    n = len(pos)
    out = np.full(n, np.nan)
    sd = np.full(n, np.nan)
    for i in range(n):
        w = pos[max(0, i - window + 1): i + 1]
        if len(w) >= min_obs:
            x = np.arange(len(w))
            out[i] = np.polyfit(x, w, 1)[0]
            sd[i] = w.std(ddof=0)
    return out, sd


def classify_stages(df: pd.DataFrame, life: pd.DataFrame, **kw) -> pd.DataFrame:
    """Rule-based stage for every song-day. Slope = rank positions/day over the last `window` chart days
    (negative = climbing). Rule priority: New Entry > Peak > Growth > Decline > Mature."""
    p = {**DEFAULT_PARAMS, **kw}
    lc = life.set_index("song_id").left_censored
    df = df.sort_values(["song_id", "date"]).copy()
    slopes, stds = [], []
    for _, grp in df.groupby("song_id", sort=False):
        s, sd = _roll_slope(grp.position.to_numpy(float), p["window"], p["min_obs"])
        slopes.append(s); stds.append(sd)
    df["rank_slope"] = np.concatenate(slopes)
    df["rank_std7"] = np.concatenate(stds)
    df["chart_age"] = df.groupby("song_id").cumcount()
    df["left_cens"] = df.song_id.map(lc)
    stage = np.full(len(df), "Mature", dtype=object)
    sl, sd, pos = df.rank_slope.to_numpy(), df.rank_std7.to_numpy(), df.position.to_numpy()
    nan = np.isnan(sl)
    stage[sl >= p["slope_thr"]] = "Decline"
    stage[sl <= -p["slope_thr"]] = "Growth"
    stage[(pos <= p["peak_max_pos"]) & (np.abs(np.nan_to_num(sl, nan=99)) < p["slope_thr"])
          & (np.nan_to_num(sd, nan=99) <= p["peak_max_std"])] = "Peak"
    stage[nan] = "Unclassified"
    new = (df.chart_age.to_numpy() < p["new_days"]) & (~df.left_cens.to_numpy().astype(bool))
    stage[new] = "New Entry"
    df["stage"] = stage
    return df


def dominant_stage(stage_df: pd.DataFrame) -> pd.Series:
    """Most frequent stage AFTER the New-Entry window; songs that never leave it are labelled 'New Entry'."""
    x = stage_df[stage_df.stage != "Unclassified"]
    post = x[x.stage != "New Entry"]
    dom = post.groupby("song_id").stage.agg(_mode)
    allsongs = x.groupby("song_id").size().index
    return dom.reindex(allsongs).fillna("New Entry")


def transition_matrix(stage_df: pd.DataFrame) -> pd.DataFrame:
    d = stage_df.sort_values(["song_id", "date"]).copy()
    d["next_stage"] = d.groupby("song_id").stage.shift(-1)
    d["next_idx"] = d.groupby("song_id").day_idx.shift(-1)
    d = d[(d.next_idx - d.day_idx == 1) & (d.stage != "Unclassified") & (d.next_stage != "Unclassified")]
    m = pd.crosstab(d.stage, d.next_stage, normalize="index")
    return m.reindex(index=[s for s in STAGES if s in m.index], columns=[s for s in STAGES if s in m.columns]).fillna(0)


# ----------------------------------------------------------------------------- churn
def daily_flow(df: pd.DataFrame, slots: int = 50) -> pd.DataFrame:
    sets = df.groupby("day_idx").song_id.agg(set)
    dates = df.groupby("day_idx").date.first()
    gap = df.groupby("day_idx").gap_before_day.first()
    top10 = df[df.position <= 10].groupby("day_idx").song_id.agg(set)
    rows, prev, prev10 = [], None, None
    for i in sets.index:
        cur = sets[i]; cur10 = top10.get(i, set())
        if prev is not None:
            ent, ex = len(cur - prev), len(prev - cur)
            rows.append(dict(day_idx=i, date=dates[i], entries=ent, exits=ex, net=ent - ex,
                             churn_rate=ent / slots, top10_new=len(cur10 - prev10),
                             top10_turnover=len(cur10 - prev10) / 10, gap_before=bool(gap[i])))
        prev, prev10 = cur, cur10
    fl = pd.DataFrame(rows)
    fl["churn_7d"] = fl.churn_rate.rolling(7, min_periods=4).mean()
    fl["month"] = fl.date.dt.to_period("M").astype(str)
    fl["weekday"] = fl.date.dt.day_name()
    return fl


def position_churn(df: pd.DataFrame) -> pd.Series:
    """Share of days on which the occupant of a rank differs from the previous day's occupant."""
    p = df.pivot(index="day_idx", columns="position", values="song_id")
    return (p != p.shift(1)).iloc[1:].mean()
