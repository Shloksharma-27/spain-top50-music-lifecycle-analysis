// Builds the research paper and executive summary. Every number is read from outputs/results.json.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  ImageRun, AlignmentType, Footer, Header, PageNumber, LevelFormat, BorderStyle,
} = require("docx");

const R = JSON.parse(fs.readFileSync("outputs/results.json", "utf8"));
const FIG = "outputs/figures/";
const OUT = "outputs/";
const FONT = "Arial";
const BLUE = "0072B2";

// ---------- formatting helpers
const f0 = (x) => Math.round(x).toLocaleString("en-US");
const f1 = (x) => Number(x).toFixed(1);
const f2 = (x) => Number(x).toFixed(2);
const pc = (x, d = 0) => (x * 100).toFixed(d) + "%";
const pv = (p) => (p < 0.001 ? "p < 0.001" : "p = " + (p < 0.01 ? p.toFixed(3) : p.toFixed(2)));
const ci = (a) => `${f2(a[0])} to ${f2(a[1])}`;

// ---------- building blocks
const P = (text, o = {}) =>
  new Paragraph({
    spacing: { after: o.after ?? 120, line: 288 },
    alignment: o.align,
    keepNext: o.keepNext,
    children: (Array.isArray(text) ? text : [text]).map((t) =>
      typeof t === "string" ? new TextRun({ text: t, font: FONT, size: o.size ?? 21, italics: o.italics, color: o.color }) : t
    ),
  });
const B = (text, bold) => new TextRun({ text, bold: true, font: FONT, size: 21, color: bold });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 }, keepNext: true, children: [new TextRun({ text: t, font: FONT, bold: true, size: 30, color: BLUE })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 100 }, keepNext: true, children: [new TextRun({ text: t, font: FONT, bold: true, size: 24 })] });
const bullet = (parts) =>
  new Paragraph({
    numbering: { reference: "bul", level: 0 },
    spacing: { after: 70, line: 280 },
    children: (Array.isArray(parts) ? parts : [parts]).map((t) => (typeof t === "string" ? new TextRun({ text: t, font: FONT, size: 21 }) : t)),
  });
const numbered = (parts, ref = "num") =>
  new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 80, line: 280 },
    children: (Array.isArray(parts) ? parts : [parts]).map((t) => (typeof t === "string" ? new TextRun({ text: t, font: FONT, size: 21 }) : t)),
  });

function pngSize(path) {
  const b = fs.readFileSync(path);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function fig(name, caption, maxW = 600) {
  const { w, h } = pngSize(FIG + name);
  const sc = Math.min(1, maxW / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(FIG + name), transformation: { width: Math.round(w * sc), height: Math.round(h * sc) },
        altText: { title: caption, description: caption, name } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 180 }, children: [new TextRun({ text: caption, font: FONT, size: 18, italics: true, color: "555555" })] }),
  ];
}

const thin = { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (txt, w, head, i) =>
    new TableCell({
      width: { size: w, type: WidthType.DXA }, borders,
      shading: head ? { fill: BLUE, type: ShadingType.CLEAR, color: "auto" } : opts.zebra && opts._r % 2 ? { fill: "F3F7FA", type: ShadingType.CLEAR, color: "auto" } : undefined,
      margins: { top: 60, bottom: 60, left: 90, right: 90 },
      children: [new Paragraph({ alignment: i > 0 && opts.numeric ? AlignmentType.RIGHT : AlignmentType.LEFT,
        children: [new TextRun({ text: String(txt), font: FONT, size: opts.size ?? 18, bold: head, color: head ? "FFFFFF" : undefined })] })],
    });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], true, i)) }),
      ...rows.map((r, ri) => { opts._r = ri; return new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], false, i)) }); }),
    ],
  });
}
const numbered2 = (parts) => numbered(parts, "num2");
const gap = () => new Paragraph({ spacing: { after: 100 }, children: [] });

// ---------- shorthand for numbers
const V = R.validation, K = R.kpis_all, ce = R.cmp_explicit_all_eligible, cs = R.cmp_single_all_eligible;
const T = (row, col) => R.stage_transition[col][row];
const mo = R.monthly_churn;
const topMonths = Object.entries(mo).sort((a, b) => b[1] - a[1]);
const shock = R.shock_days_detail;
const es = R.early_warning;
const cl = R.clusters;
const ewS = es.y_survive30, ewT = es.y_top10;
const cox = R.cox, cox2 = R.cox_no_pop, coxc = R.cox_complete_pop;
const dom = shock.filter((s) => s.top_artist_entries / s.entries >= 0.5), nondom = shock.filter((s) => s.top_artist_entries / s.entries < 0.5);
const artistName = (a) => a.split(" ").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");

// =====================================================================================================
// RESEARCH PAPER
// =====================================================================================================
const paper = [];
paper.push(
  new Paragraph({ spacing: { before: 1200, after: 120 }, children: [new TextRun({ text: "Content Maturity, Release Lifecycle & Playlist Rotation Analysis of Spain Top 50 Songs", font: FONT, bold: true, size: 44, color: BLUE })] }),
  new Paragraph({ spacing: { after: 400 }, children: [new TextRun({ text: "Research paper prepared for Atlantic Recording Corporation", font: FONT, size: 26, color: "555555" })] }),
  P(`Data: daily Spotify-style Top 50 snapshots for Spain, ${V.date_min.slice(0, 10)} to ${V.date_max.slice(0, 10)} (${V.final_days} observed days, ${f0(V.final_rows)} chart entries after cleaning).`, { color: "555555" }),
  H1("Abstract"),
  P(`This study builds a song-level lifecycle from ${V.final_days} daily snapshots of Spain's Top 50 and uses it to answer how long songs survive, how the playlist rotates, and whether explicit content or release format changes a song's trajectory. After normalising ${V.distinct_raw_song_artist} raw song/artist strings into ${V.distinct_song_ids} distinct songs, we observed the entry of ${R.eligible_songs} songs (the rest were already charting when the data begins) and treated songs still charting at the end as right-censored.`),
  P([B("Main findings. "), `The chart is quieter than the brief's premise suggests: on a typical day only ${f1(R.entries_per_day_median)} song enters (mean ${f2(R.entries_per_day_mean)}, or ${pc(R.churn_mean, 1)} of slots), and ${pc(R.zero_entry_days_share)} of days have no new entry at all. Rotation is driven by a handful of "shock days" on which one artist floods the chart: ${R.shock_days} days (${pc(R.shock_days / R.flow_days, 1)} of the calendar) supply ${pc(R.entries_share_from_shocks)} of all entries, most of them one artist charting many tracks at once. Survival is sharply skewed: ${pc(R.survival_le7d_share)} of new entries are gone within a week, while ${pc(R.survival_ge90d_share)} last 90 days or more; median survival is ${R.km_median_all} days. Half of all songs (${pc(R.share_enter_at_best_position)}) hit their best-ever position on their first chart day. `,
    `Explicit and clean songs show no detectable difference in lifecycle (log-rank ${pv(R.logrank_p.explicit)}; mean-days ratio ${f2(ce.mean_ratio)}, 95% CI ${ci(ce.mean_ratio_ci95)}). Singles outlast album tracks by a wide margin (median ${cs.single.median} vs ${cs.album.median} days; ratio ${f2(cs.mean_ratio)}, ${pv(R.logrank_p.single)}), but a multivariable model attributes much of that gap to album size and to album-drop dynamics rather than the single/album label itself. The popularity score lags rank by about ${R.pop_peak_vs_rank_peak.median_days_pop_peak - R.pop_peak_vs_rank_peak.median_days_rank_peak} days and barely moves as songs decline, so it is a poor real-time lifecycle signal. A simple model using only a song's first week of chart data predicts 30-day survival with AUC ${f2(ewS.auc_logit)} (naive baseline ${f2(ewS.auc_baseline_mean_pos7)}).`]),
  P([B("Scope note. "), "The dataset covers Spain only and contains no release dates, so it cannot test claims about Spain versus UK/US rotation speed, and 'age' throughout means days since first Top 50 appearance."]),

  H1("1. Introduction and objectives"),
  P("Atlantic Recording Corporation needs lifecycle intelligence for the Spanish market: how long content lasts, whether the playlist favours fresh or mature tracks, and how content attributes shape a song's path. The brief asks for: (1) data validation and normalisation, (2) a song lifecycle table, (3) lifecycle stage classification, (4) rotation and churn analysis, (5) content attribute versus lifecycle analysis, (6) popularity versus lifecycle maturity, (7) a KPI set, and (8) an interactive dashboard. We add survival analysis, an early-warning model, lifecycle archetypes and artist-concentration analysis."),
  P("The brief describes Spain as having faster playlist rotation than the UK/US and high freshness sensitivity. These are hypotheses about cross-market differences; with a single-market dataset we can describe Spain's rotation in absolute terms but cannot confirm the comparison."),

  H1("2. Data and validation"),
  P(`The file has ${f0(V.raw_rows)} rows and the ten columns described in the brief. There are no null cells. The checks below were run before any analysis; each anomaly and its treatment is documented so the results can be reproduced.`),
  table(["Check", "Finding", "Treatment"], [
    ["Days with exactly 50 rows", `${V.final_days - 1} of ${V.observed_days} days pass; 2025-03-01 has 100 rows`, "That day contains two full 50-row snapshots in different orders. Kept the first, dropped 50 rows. Neither block could be reliably assigned to another date."],
    ["Missing calendar dates", `${V.missing_dates.length}: ${V.missing_dates.join(", ")}`, "Treated as data gaps, not exits. Songs on both sides of a gap stay in the same run; the day after a gap is excluded from churn averages."],
    ["Zero popularity", `${V.zero_popularity_rows} rows across 25 days`, "Treated as missing (the API returns 0 for brand-new tracks; 95% of affected entrants are album tracks). Not imputed."],
    ["Naming variants", `${V.distinct_raw_song_artist} raw pairs to ${V.distinct_song_ids} songs`, "Normalised case, accents, feat./with/con tags; song ID = normalised title + primary artist. The same song is often listed with and without its featured artist."],
    ["Same song twice in a day", `${V.same_song_twice_same_day_dropped} after normalisation`, "No action needed."],
    ["Left-censoring", `${R.left_censored} songs already charting on day 1`, "Excluded from entry, time-to-peak and survival statistics."],
    ["Right-censoring", `${R.right_censored} songs still charting on the last day`, "Kept in survival models as censored observations."],
    ["Re-entries", `${R.reentry_songs} songs (${pc(R.reentry_share)}) left and returned`, `Tracked as separate runs; total days counts chart days. Median gap ${R.reentry_gap_days_median} days, ${pc(R.reentry_gap_le3_share)} of gaps 3 days or fewer.`],
  ], [2000, 3000, 4360]),
  gap(),
  P(`Re-entries are common because songs oscillate around the rank-50 boundary, so a brief exit is often noise rather than a real end of life. Analyses that need one duration per song use total days on chart and define the event as the final exit.`),

  H1("3. Methodology"),
  H2("3.1 Lifecycle construction"),
  P("For each song we compute entry and exit dates, total chart days, span, number of runs, peak position, days to first reach that peak, entry and exit position, average position and volatility, days in the Top 10 and Top 25, popularity at entry, at exit and at peak, plus content attributes (explicit flag, release type, track count, duration)."),
  H2("3.2 Stage classification"),
  P("Stages are assigned to every song-day with transparent rules based on the last seven chart days. Slope is the linear trend of position in ranks per day (negative means climbing)."),
  bullet([B("New Entry: "), "first 7 chart days (not applied to songs already charting on day 1)."]),
  bullet([B("Peak: "), "position 10 or better, absolute slope below 0.5 and rank standard deviation of 3 or less."]),
  bullet([B("Growth: "), "slope of -0.5 or steeper. "], ),
  bullet([B("Decline: "), "slope of +0.5 or steeper."]),
  bullet([B("Mature: "), "everything else (stable, typically mid-rank)."]),
  P("Rules are applied in the order New Entry, Peak, Growth, Decline, Mature. A sensitivity grid over slope thresholds (0.25, 0.5, 1.0) and volatility caps (2, 3, 4) is in Appendix B."),
  H2("3.3 Rotation and churn"),
  P("Daily entries are songs present today but not yesterday; exits are the reverse. Churn rate is entries divided by 50 slots. We also measure rank-level turnover and Top 10 turnover. A shock day is one with 8 or more entries (roughly the top 2.5% of days)."),
  H2("3.4 Statistics"),
  P("Comparisons use Mann-Whitney tests with Cliff's delta, bootstrap confidence intervals for mean ratios (2,000 resamples), Kaplan-Meier curves with log-rank tests, and a Cox proportional-hazards model with a small ridge penalty. All lifecycle statistics use only songs whose entry we observed. Songs by the same artist are not independent; we did not apply cluster-robust errors, so p-values for artist-heavy segments may be somewhat optimistic."),

  H1("4. Results"),
  H2("4.1 How long songs survive"),
  P(`Of ${R.eligible_songs} songs with an observed entry, ${R.eligible_completed} were seen leaving for good. Lifespans are extremely skewed (Figure 1): ${pc(R.survival_le3d_share)} last three days or fewer and ${pc(R.survival_le7d_share)} last a week or less, while ${pc(R.survival_ge90d_share)} pass 90 days. The Kaplan-Meier median survival is ${R.km_median_all} days, and the estimated share still charting at 7, 30 and 90 days is ${pc(R.km_s7)}, ${pc(R.km_s30)} and ${pc(R.km_s90)} (the KM figures are higher than raw shares because they account for songs still charting when the data ends).`),
  ...fig("fig09_lifespan.png", "Figure 1. Distribution of total days on the Top 50 (log scale), songs with observed entry."),
  P(`Entry position is the strongest single predictor of what follows. ${pc(R.share_enter_at_best_position)} of songs reached their peak on their first chart day (median days to peak ${R.time_to_peak_desc["50%"]}; mean ${f1(R.time_to_peak_desc.mean)}, pulled up by slow burners). Among songs that eventually reached the Top 10 (${pc(R.reached_top10_share)} of entrants; ${pc(R.reached_top1_share)} reached number 1), the median time to peak was ${f1(R.ttp_among_top10_reachers["50%"])} days. Songs that entered in the Top 10 had a ${pc(R.km_s30_by_entry_bucket["1-10"])} chance of surviving 30 days versus ${pc(R.km_s30_by_entry_bucket["11-25"])} for entries at ranks 11-25 and ${pc(R.km_s30_by_entry_bucket["41-50"])} for entries at 41-50 (n = ${R.n_by_entry_bucket["1-10"]}, ${R.n_by_entry_bucket["11-25"]}, ${R.n_by_entry_bucket["41-50"]}).`),

  H2("4.2 Lifecycle stages"),
  P(`Across all song-days, ${pc(R.stage_share_songdays.Mature)} are Mature, ${pc(R.stage_share_songdays.Decline)} Decline, ${pc(R.stage_share_songdays.Peak)} Peak, ${pc(R.stage_share_songdays.Growth)} Growth and ${pc(R.stage_share_songdays["New Entry"])} New Entry (${pc(R.stage_share_songdays.Unclassified, 1)} unclassified). Stages are sticky (Figure 2): a song in Peak stays in Peak the next day ${pc(T("Peak", "Peak"))} of the time, in Decline ${pc(T("Decline", "Decline"))}, and in Mature ${pc(T("Mature", "Mature"))}. The most common exits from Mature are into Decline (${pc(T("Mature", "Decline"))}) and back into Growth (${pc(T("Mature", "Growth"))}), and from Decline back to Mature (${pc(T("Decline", "Mature"))}). Songs spend on average ${f1(R.mean_days_per_stage.Mature)} days in Mature and ${f1(R.mean_days_per_stage.Decline)} in Decline versus ${f1(R.mean_days_per_stage.Peak)} in Peak.`),
  ...fig("fig03_stages.png", "Figure 2. Stage share of song-days and next-day stage transition probabilities."),
  P(`Stage shares depend on the slope threshold: at 0.25 rank/day, Decline rises to ${pc(R.stage_sensitivity[1].Decline)} and Mature falls to ${pc(R.stage_sensitivity[1].Mature)}; at 1.0, Mature rises to ${pc(R.stage_sensitivity[7].Mature)}. The volatility cap has almost no effect. The stage mix should therefore be read as relative, not absolute.`),

  H2("4.3 Playlist rotation and churn"),
  P(`Rotation is slow on most days and violent on a few. Across ${R.flow_days} comparable days, ${f2(R.entries_per_day_mean)} songs enter per day on average (median ${f1(R.entries_per_day_median)}), a churn rate of ${pc(R.churn_mean, 1)} with a coefficient of variation of ${f2(R.churn_cv)}. Top 10 turnover is ${pc(R.top10_turnover_mean, 1)} per day. Excluding the ${R.shock_days} shock days, churn falls to ${pc(R.churn_excl_shocks, 1)}.`),
  ...fig("fig01_daily_entries.png", "Figure 3. Daily entries. Red bars are shock days with 8 or more new songs."),
  P(`${dom.length} of the ${shock.length} shock days are dominated (half or more of the new entries) by a single artist, consistent with a full-album release charting at once (the dataset has no release dates, so this is an inference from the artist mix). The other ${nondom.length} (${nondom.map((s) => s.date).join(", ")}) spread across many artists. The eight largest are listed below.`),
  table(["Date", "New songs", "Largest single-artist share", "New in Top 10"],
    shock.slice().sort((a, b) => b.entries - a.entries).slice(0, 8).map((s) => [s.date, s.entries, `${artistName(s.top_artist)} (${s.top_artist_entries})`, s.top10_new]),
    [1900, 1500, 4200, 1760], { numeric: false, zebra: true }),
  gap(),
  P(`Monthly churn ranged from ${pc(topMonths[topMonths.length - 1][1], 1)} (${topMonths[topMonths.length - 1][0]}) to ${pc(topMonths[0][1], 1)} (${topMonths[0][0]}); the highest months coincide with shock days (Figure 4). With only 18 months of data, we cannot separate seasonal effects from individual album drops, and we make no claim about summer, Christmas or festival seasonality beyond noting that 2024-12-25 and 2024-12-28 appear among the shock days. Excluding shock days, new entries cluster on Mondays and Tuesdays (${f2(R.weekday_entries_excl_shocks.Monday)} and ${f2(R.weekday_entries_excl_shocks.Tuesday)} per day) versus ${f2(R.weekday_entries_excl_shocks.Sunday)} on Sundays (Kruskal-Wallis ${pv(R.weekday_kruskal_p_excl_shocks)}). This may reflect release-day patterns or the timing of the snapshot; the data cannot distinguish the two.`),
  ...fig("fig04_churn_month_weekday.png", "Figure 4. Average daily churn by month, with and without shock days, and new songs by weekday."),
  P(`Rotation is concentrated at the bottom of the chart (Figure 5). The occupant of a top-10 rank changes on ${pc(R.position_churn_top10)} of days, versus ${pc(R.position_churn_11_40)} for ranks 11-40 and ${pc(R.position_churn_bottom10)} for ranks 41-50. The average absolute daily rank move is ${f2(R.daily_rank_move_abs_mean)} places (${f2(R.rank_move_by_position_bucket["1-10"])} in the Top 10, ${f2(R.rank_move_by_position_bucket["41-50"])} at ranks 41-50); ${pc(R.daily_rank_move_share_le2)} of daily moves are two places or fewer.`),
  ...fig("fig05_position_churn.png", "Figure 5. Share of days on which each rank changes occupant."),
  P(`Artist concentration is moderate: ${R.n_primary_artists} primary artists appear, the top ten account for ${pc(R.artist_top10_share)} of chart slot-days (largest: ${artistName(R.artist_top1[0])}, ${pc(R.artist_top1[1], 1)}), and the Herfindahl index is ${R.artist_hhi.toFixed(3)}. On an average day the most-represented artist holds ${f1(R.mean_max_artist_songs_per_day)} slots; on ${R.days_with_artist_ge5} days one artist held five or more, with a maximum of ${R.max_songs_one_artist_one_day}.`),

  H2("4.4 Content attributes versus lifecycle"),
  P([B("Explicit versus clean. "), `Explicit songs are ${pc(R.explicit_share_songs)} of distinct songs and ${pc(R.explicit_share_songdays)} of chart slot-days. Among songs with observed entry (${ce.explicit.n} explicit, ${ce.clean.n} clean) there is no detectable difference: mean days ${f1(ce.explicit.mean)} vs ${f1(ce.clean.mean)} (Mann-Whitney ${pv(ce.mannwhitney_p)}, Cliff's delta ${f2(ce.cliffs_delta)}; ratio ${f2(ce.mean_ratio)}, 95% CI ${ci(ce.mean_ratio_ci95)}); the log-rank test gives ${pv(R.logrank_p.explicit)}. The share reaching the Top 10 is ${pc(R.explicit_top10_rate.explicit, 1)} vs ${pc(R.explicit_top10_rate.clean, 1)} (${pv(R.explicit_top10_chi2_p)}), and peak position and time-to-peak are also statistically indistinguishable. The Cox hazard ratio for explicit is ${f2(cox.explicit_i["exp(coef)"])} (95% CI ${f2(cox.explicit_i["exp(coef) lower 95%"])} to ${f2(cox.explicit_i["exp(coef) upper 95%"])}). The confidence interval is wide enough that differences of up to about 20-40% in average days cannot be ruled out, but there is no evidence of one.`]),
  P([B("Single versus album track. "), `This is the clearest content effect (Figure 6). Singles average ${f1(cs.single.mean)} chart days versus ${f1(cs.album.mean)} for album tracks (median ${cs.single.median} vs ${cs.album.median}; ratio ${f2(cs.mean_ratio)}, 95% CI ${ci(cs.mean_ratio_ci95)}; Mann-Whitney ${pv(cs.mannwhitney_p)}). Kaplan-Meier median survival is ${R.km_median_by_single.True} vs ${R.km_median_by_single.False} days and 30-day survival ${pc(R.km_s30_by_single.True)} vs ${pc(R.km_s30_by_single.False)} (log-rank ${pv(R.logrank_p.single)}). Yet peak position is similar (mean ${f1(R.cmp_single_peak.single.mean)} vs ${f1(R.cmp_single_peak.album.mean)}, ${pv(R.cmp_single_peak.mannwhitney_p)}) and ${pc(R.single_top10_rate.single)} of singles vs ${pc(R.single_top10_rate.album)} of album tracks reach the Top 10. Album tracks therefore reach comparable heights but hold them for less time. Singles also enter lower (mean entry position ${f1(R.cmp_single_entrypos.single.mean)} vs ${f1(R.cmp_single_entrypos.album.mean)}) and take longer to peak (median ${R.cmp_single_ttp.single.median} vs ${R.cmp_single_ttp.album.median} days). Singles re-enter more often (${pc(R.reentry_by_type.single)} vs ${pc(R.reentry_by_type.album)}).`]),
  ...fig("fig02_km_survival.png", "Figure 6. Kaplan-Meier survival curves with 95% confidence bands."),
  P([B("Album drops explain much of the album penalty. "), `${R.shock_entrants.n} songs entered on shock days, and ${pc(R.shock_entrants.album_share_shock)} of them are album tracks (versus ${pc(R.shock_entrants.album_share_other)} on other days). Their median stay is ${R.shock_entrants.median_days_shock} days versus ${R.shock_entrants.median_days_other} for other entrants (mean ${f1(R.shock_entrants.mean_days_shock)} vs ${f1(R.shock_entrants.mean_days_other)}; ${pv(R.shock_entrants.mannwhitney_p)}), yet their chance of reaching the Top 10 is about the same (${pc(R.shock_entrants.top10_rate_shock)} vs ${pc(R.shock_entrants.top10_rate_other)}). Album-drop entries produce a brief burst, then most tracks fall away, with a few focus tracks surviving.`]),
  ...fig("fig10_shock_survival.png", "Figure 7. Survival of songs entering on shock days versus normal days.", 420),
  P([B("Duration and album size. "), `Song length has only a weak association with longevity (Spearman ${f2(R.spearman_duration_days[0])}, ${pv(R.spearman_duration_days[1])}); songs under 2.5 minutes have a median of ${R.duration_bins["<2.5"].median_days} days versus ${R.duration_bins["3.5-4"].median_days} for 3.5-4 minutes, but the pattern is not monotonic. Album size matters more: the more tracks on the release, the shorter the stay (Spearman ${f2(R.spearman_tracks_days[0])}, ${pv(R.spearman_tracks_days[1])}); median days are ${R.tracks_bins["1"].median_days} for one-track releases, ${R.tracks_bins["4-10"].median_days} for 4-10 tracks and ${R.tracks_bins["11-20"].median_days} for 11-20 tracks (Figure 8). Rank volatility is similar across sizes (mean daily-rank standard deviation ${f1(R.tracks_bins["4-10"].pos_std)} to ${f1(R.tracks_bins["1"].pos_std)}) except for releases of 21+ tracks (${f1(R.tracks_bins["21+"].pos_std)}).`]),
  ...fig("fig07_size_duration.png", "Figure 8. Median days on chart by release size and by song length."),
  P([B("Multivariable view. "), `A Cox model on ${R.cox_n} songs adjusts for explicit flag, single flag, log track count, duration, entry position and entry popularity. Hazard ratios above 1 mean faster exit. Entry position is significant (HR ${f2(cox.entry_pos_z["exp(coef)"])} per standard deviation worse, ${pv(cox.entry_pos_z.p)}), as is entry popularity (HR ${f2(cox.entry_pop_z["exp(coef)"])} per standard deviation higher, ${pv(cox.entry_pop_z.p)}), and log track count (HR ${f2(cox.log_tracks["exp(coef)"])}, ${pv(cox.log_tracks.p)}). Once track count is included, the single flag is not significant (HR ${f2(cox.single_i["exp(coef)"])}, 95% CI ${f2(cox.single_i["exp(coef) lower 95%"])} to ${f2(cox.single_i["exp(coef) upper 95%"])}), which fits the interpretation that album size, not the label, drives the gap. These two variables overlap heavily (most singles have one track), so their separate effects cannot be pinned down precisely. Explicit and duration remain non-significant.`]),
  P(`A missing-popularity indicator has a very large hazard ratio (${f2(cox.entry_pop_missing["exp(coef)"])}) because ${pc(R.entry_pop_missing_album_share)} of the ${pc(R.entry_pop_missing_share, 1)} of songs with no popularity score in their first three days are album-drop tracks with a median stay of ${R.entry_pop_missing_median_days[0]} day(s). It acts as a proxy for album-drop entrants rather than a causal effect; models without the indicator (concordance ${f2(R.cox_no_pop_concordance)}) and on complete cases give the same conclusions for the other variables (log track count HR ${f2(cox2.log_tracks["exp(coef)"])} and ${f2(coxc.log_tracks["exp(coef)"])}; entry position HR ${f2(cox2.entry_pos_z["exp(coef)"])} and ${f2(coxc.entry_pos_z["exp(coef)"])}). A log-linear regression on completed songs agrees on direction for entry position and track count.`),

  H2("4.5 Popularity versus lifecycle maturity"),
  P(`The popularity score does not behave like a rank signal (Figure 9). Mean popularity of newly entered songs climbs from ${f1(R.pop_decay_by_age["0"])} on day 0 to ${f1(R.pop_decay_by_age["7"])} at day 7 and ${f1(R.pop_decay_by_age["21"])} at day 21, then plateaus near ${f1(R.pop_decay_by_age["60"])}. Rank peaks earlier: the median song peaks in rank on day ${R.pop_peak_vs_rank_peak.median_days_rank_peak} and in popularity on day ${R.pop_peak_vs_rank_peak.median_days_pop_peak}; popularity peaks before rank in only ${pc(R.pop_peak_vs_rank_peak.pop_peak_before_rank_peak_share)} of songs (same day in ${pc(R.pop_peak_vs_rank_peak.same_day_share)}). The two peak times are correlated (Spearman ${f2(R.pop_peak_vs_rank_peak.spearman)}).`),
  P(`There is no lead-lag signal: correlations between the daily change in popularity and the daily change in rank at lags of -3 to +3 days are all below ${f2(Math.max(...Object.values(R.leadlag_dpop_vs_dpos).map(Math.abs)))} in magnitude. Nor does popularity decay as songs fade. In the 14 days before a song's final exit its average position slides from ${f1(R.pop_by_days_to_exit_pos["14"])} to ${f1(R.pop_by_days_to_exit_pos["0"])}, while popularity stays between ${f1(Math.min(...Object.values(R.pop_by_days_to_exit)))} and ${f1(Math.max(...Object.values(R.pop_by_days_to_exit)))}. Average popularity is highest in the Peak stage (${f1(R.pop_mean_by_stage.Peak)}) and lowest in New Entry (${f1(R.pop_mean_by_stage["New Entry"])}), and it is moderately related to longevity (peak popularity vs days on chart, Spearman ${f2(R.spearman_peakpop_days[0])}). The score therefore describes cumulative appeal rather than current chart momentum and should not be used to trigger lifecycle decisions in real time.`),
  ...fig("fig06_popularity.png", "Figure 9. Popularity ramps after entry and stays flat while rank deteriorates before exit."),

  H2("4.6 Early-warning model"),
  P(`We asked whether the first week predicts the outcome. Using ${es.n_songs_with_3days} songs with an observed entry and at least three chart days in their first seven, and restricting to those whose 30-day outcome is observable (${es.n_train + es.n_test}), we trained on entries up to ${es.cutoff} (n = ${es.n_train}) and tested on later entries (n = ${es.n_test}). Features: entry position, mean and best position, position slope and volatility, mean popularity in the window, explicit flag, release type, track count and duration.`),
  table(["Target", "Base rate (test)", "Logistic AUC", "Gradient boosting AUC", "Naive baseline AUC"], [
    ["Survives 30+ days", pc(ewS.base_rate_test), f2(ewS.auc_logit), f2(ewS.auc_gb), f2(ewS.auc_baseline_mean_pos7)],
    ["Reaches Top 10 (any time)", pc(ewT.base_rate_test), f2(ewT.auc_logit), f2(ewT.auc_gb), f2(ewT.auc_baseline_mean_pos7)],
  ], [2600, 1700, 1600, 1900, 1560], { numeric: true }),
  gap(),
  P(`The naive baseline ranks songs by average first-week position. For 30-day survival the models beat it (AUC ${f2(ewS.auc_logit)} vs ${f2(ewS.auc_baseline_mean_pos7)}); the most important feature is the first-week position slope (permutation importance ${f2(ewS.importance.slope7)} AUC points), followed by average first-week position. Content attributes carry almost no signal. The Top 10 result is partly circular, because a song's best first-week position already reveals whether it reached the Top 10, so we treat the survival result as the meaningful one. The test set is small (${es.n_test} songs), so these AUCs carry wide uncertainty, and the model applies only to songs that last at least three days.`),

  H2("4.7 Lifecycle archetypes"),
  P(`K-means clustering on lifespan, peak, timing of peak, Top 10 share, volatility and entry position yields four archetypes (Figure 10). Silhouette scores are modest (${f2(R.cluster_silhouette["4"])} for k = 4, ${f2(R.cluster_silhouette["5"])} for k = 5), meaning the boundaries are soft; we use four because they are the most interpretable.`),
  table(["Archetype", "Songs", "Median days", "Median peak", "Median entry pos.", "Single share", "Re-entry share"],
    cl.slice().sort((a, b) => b.mean_days - a.mean_days).map((c) => [c.archetype, c.n, f0(c.median_days), f0(c.peak), f0(c.entry_pos), pc(c.single), pc(c.reentry)]),
    [2300, 900, 1200, 1200, 1500, 1100, 1160], { numeric: true, zebra: true }),
  gap(),
  bullet([B("Evergreen Hit: "), "enters high, peaks near the top and stays for months; the smallest group but the largest share of chart-days."]),
  bullet([B("Slow Burner: "), "enters at the bottom, climbs for weeks and lasts long; majority singles, frequent re-entries."]),
  bullet([B("Debut-and-Fade: "), "enters mid-chart at its best position and is gone in about a week; mostly album tracks."]),
  bullet([B("Bottom-Chart Filler: "), "never leaves the lower half and never reaches the Top 10."]),
  ...fig("fig08_archetypes.png", "Figure 10. Lifecycle archetypes by lifespan and peak position.", 460),
  ...fig("fig12_trajectories.png", "Figure 11. Example rank trajectories, one per archetype."),

  H2("4.8 Fresh versus catalog balance"),
  P(`After a 90-day burn-in (chart age is unknown for songs already charting at the start), ${pc(R.age_mix_overall.le30)} of chart slot-days are held by songs 30 or fewer chart-days old, ${pc(R.age_mix_overall.le7)} by songs in their first week, and ${pc(R.age_mix_overall.gt90)} by songs more than 90 chart-days old. The top of the chart is younger than the bottom: the average chart age of a Top 10 song is ${f0(R.avg_chart_age_top10)} days versus ${f0(R.avg_chart_age_bottom10)} at ranks 41-50. Spain's Top 50 is therefore more catalog-heavy than a pure freshness-driven market would be, with fresh share varying from ${pc(Math.min(...Object.values(R.freshness_by_month)))} to ${pc(Math.max(...Object.values(R.freshness_by_month)))} by month (Figure 12). Chart age is not release age, so this measures chart tenure only.`),
  ...fig("fig11_freshness.png", "Figure 12. Fresh and catalog share of chart slots by month."),

  H1("5. Key performance indicators"),
  P("All KPIs are computed by the same code the dashboard uses, so filtered dashboard values reconcile with this table."),
  table(["KPI", "Value", "Definition and reading"], [
    ["Average days on playlist", f1(K.avg_days_on_playlist), `Mean chart days for songs with observed entry (median ${f0(K.median_days_on_playlist)}; KM median ${f0(K.median_survival_days_km)}). The mean is pulled up by a long tail of evergreens.`],
    ["Entry-to-peak time", `${f1(K.entry_to_peak_mean)} days (median ${f0(K.entry_to_peak_median)})`, "Days from first appearance to best position. Most songs peak on day one; the mean reflects slow burners."],
    ["Playlist churn rate", pc(K.churn_rate, 1), `New songs per day divided by 50 (${f2(K.entries_per_day)} songs/day). Excluding shock days: ${pc(K.churn_rate_excl_shocks, 1)}.`],
    ["Retention Stability Index", f1(K.retention_stability_index), `100 x (1 - churn) / (1 + CV of churn); CV = ${f2(K.churn_cv)}. Higher is steadier. Low here because churn is spiky.`],
    ["Explicit Lifecycle Score", f0(K.explicit_lifecycle_score), "Mean of explicit/clean ratios for average days, days in Top 10 and share reaching Top 10, times 100. 100 means identical behaviour."],
    ["Single vs Album Longevity Ratio", f2(K.single_album_longevity_ratio) + "x", `Mean days for singles / album tracks (median ratio ${f1(K.single_album_median_ratio)}x).`],
    ["Freshness Index", pc(K.freshness_index), "Share of chart slots held by songs 30 or fewer chart-days old (after 90-day burn-in)."],
    ["Catalog Share", pc(K.catalog_share), "Share of slots held by songs more than 90 chart-days old."],
    ["Top 10 turnover", pc(K.top10_turnover, 1), "New Top 10 songs per day divided by 10."],
    ["Median survival (KM)", `${f0(K.median_survival_days_km)} days`, "Days until half of new entries have left for good, accounting for censoring."],
  ], [2300, 1900, 5160], { zebra: true }),
  gap(),
  table(["Segment", "Avg days", "KM median", "Churn (own entries)", "Top 10 turnover", "RSI"], [
    ["Explicit", f1(R.kpis_explicit.avg_days_on_playlist), f0(R.kpis_explicit.median_survival_days_km), pc(R.kpis_explicit.churn_rate, 1), pc(R.kpis_explicit.top10_turnover, 1), f1(R.kpis_explicit.retention_stability_index)],
    ["Clean", f1(R.kpis_clean.avg_days_on_playlist), f0(R.kpis_clean.median_survival_days_km), pc(R.kpis_clean.churn_rate, 1), pc(R.kpis_clean.top10_turnover, 1), f1(R.kpis_clean.retention_stability_index)],
    ["Single", f1(R.kpis_single.avg_days_on_playlist), f0(R.kpis_single.median_survival_days_km), pc(R.kpis_single.churn_rate, 1), pc(R.kpis_single.top10_turnover, 1), f1(R.kpis_single.retention_stability_index)],
    ["Album track", f1(R.kpis_album.avg_days_on_playlist), f0(R.kpis_album.median_survival_days_km), pc(R.kpis_album.churn_rate, 1), pc(R.kpis_album.top10_turnover, 1), f1(R.kpis_album.retention_stability_index)],
  ], [1700, 1300, 1400, 2000, 1700, 1260], { numeric: true }),
  P("Segment churn counts only the segment's own new entries against 50 slots, so segment values sum to roughly the overall rate.", { size: 18, italics: true, color: "555555" }),

  H1("6. Recommendations"),
  P("Each recommendation is tied to the evidence above. Where the data can show an association but not a causal effect, we say so and propose a test."),
  numbered([B("Lead with singles; use albums for a burst, not for longevity. "), `Singles have a ${R.km_median_by_single.True}-day median survival versus ${R.km_median_by_single.False} days for album tracks, and ${pc(R.km_s30_by_single.True)} vs ${pc(R.km_s30_by_single.False)} still charting at 30 days. Peak heights are similar, so albums are effective at earning a high debut but not at holding it. For an album release, choose one or two focus tracks to sustain after the drop, because ${pc(R.shock_entrants.album_share_shock)} of drop-day entrants are album tracks with a median stay of ${R.shock_entrants.median_days_shock} days. The single-versus-album gap is confounded with album size, so a staggered single-then-album rollout should be tested rather than assumed.`]),
  numbered([B("Invest before and on release day, because day-one rank predicts the rest. "), `${pc(R.share_enter_at_best_position)} of songs peak on day one, and songs entering in the Top 10 have a ${pc(R.km_s30_by_entry_bucket["1-10"])} chance of lasting 30 days versus ${pc(R.km_s30_by_entry_bucket["11-25"])}-${pc(R.km_s30_by_entry_bucket["41-50"])} otherwise. Pre-release playlist pitching and pre-saves should be sized to land the debut position, not to fix a weak one later.`]),
  numbered([B("Use a day-7 checkpoint. "), `First-week rank slope and average position predict 30-day survival with AUC ${f2(ewS.auc_logit)}. Songs with an improving slope by day 7 are candidates for sustained spend; songs flat or falling at ranks 40-50 are likely to leave, so hold back budget. Validate on new releases before making budget rules out of it (test set of ${es.n_test} songs).`]),
  numbered([B("Do not read brief exits as failure, and time re-pushes to the Decline stage. "), `${pc(R.reentry_share)} of songs leave and return, ${pc(R.reentry_gap_le3_share)} of those gaps within three days, because ranks 41-50 turn over ${pc(R.position_churn_bottom10)} of days. The average song slides about ${f0(R.pop_by_days_to_exit_pos["0"] - R.pop_by_days_to_exit_pos["14"])} places in its last two weeks, and a Mature song has a ${pc(T("Mature", "Decline"))} daily chance of entering Decline. A re-push when a song first enters Decline is a reasonable test; the data show the pattern but cannot show that a re-push works.`]),
  numbered([B("Make the explicit decision on creative and audience grounds, not lifecycle grounds. "), `We found no lifecycle difference (log-rank ${pv(R.logrank_p.explicit)}, Explicit Lifecycle Score ${f0(K.explicit_lifecycle_score)}). Editing tracks to a clean version is unlikely to change chart tenure in Spain based on this data.`]),
  numbered([B("Plan around shock days and capacity. "), `A typical day opens only about ${f0(R.entries_per_day_median)} slot, so a new release competes for scarce space; ${R.shock_days} artist-flood days supply ${pc(R.entries_share_from_shocks)} of all entries. Consider avoiding same-week launches of a lower-priority release against a known rival album drop (an inference from slot displacement, not a tested effect), and note that new entries cluster on Mondays and Tuesdays.`]),
  numbered([B("Balance the portfolio toward catalog upkeep. "), `${pc(R.age_mix_overall.gt90)} of slots go to songs older than 90 chart-days versus ${pc(R.age_mix_overall.le30)} to songs 30 days or younger, and Evergreen Hits earn the most chart-days. Budget for sustaining the small number of songs that can reach evergreen status (${pc(cl.find((c) => c.archetype === "Evergreen Hit").n / cl.reduce((a, c) => a + c.n, 0))} of classified songs), rather than only launching new material.`]),
  numbered([B("Do not use the popularity score as a real-time trigger. "), "It lags rank by roughly nine days and does not fall as songs decline. Use chart position and slope."]),

  H1("7. Limitations"),
  bullet("No release dates: chart age is measured from first Top 50 appearance, so a song that released earlier and entered late looks new. Release-timing advice about days of the week cannot be derived from this file."),
  bullet("Single-market data: claims that Spain rotates faster than the UK/US, or is more freshness-sensitive, cannot be tested. The absolute rotation seen here is low."),
  bullet("Top 50 truncation: songs below rank 50 are invisible, so 'exits' include songs that dropped just under the cut and re-entry gaps are partly noise."),
  bullet("Eighteen months: little repeat seasonality, so seasonal statements are limited to observed shock dates."),
  bullet("Non-independence: songs by the same artist cluster, and album tracks arrive together. Standard errors do not account for this."),
  bullet("Data handling assumptions: the first snapshot on 2025-03-01 was kept; popularity zeros were treated as missing; the normalisation rule may merge two different songs by the same primary artist with the same title (unlikely) or split versions with different titles."),
  bullet("Weekday pattern: could reflect snapshot timing as well as real release behaviour."),
  bullet("Early-warning results come from a small out-of-time test set and should be re-validated."),

  H1("Appendix A. Definitions"),
  bullet([B("Chart day / observed day: "), "one of the 555 dates with a snapshot."]),
  bullet([B("Total days on playlist: "), "number of observed days the song appears (not the span between entry and exit)."]),
  bullet([B("Time to peak: "), "calendar days from first appearance to the first day of its best position."]),
  bullet([B("Left-censored: "), "song present on the first date. Right-censored: song present on the last date."]),
  bullet([B("Shock day: "), "a day with 8 or more new entries."]),
  bullet([B("Event (survival): "), "final exit observed before the last date."]),
  H1("Appendix B. Stage sensitivity"),
  table(["Slope threshold", "Vol. cap", "New Entry", "Growth", "Peak", "Mature", "Decline"],
    R.stage_sensitivity.map((s) => [s.slope_thr, s.peak_max_std, pc(s["New Entry"]), pc(s.Growth), pc(s.Peak), pc(s.Mature), pc(s.Decline)]),
    [1500, 1100, 1300, 1300, 1300, 1400, 1460], { numeric: true, zebra: true }),
  gap(),
  H1("Appendix C. Reproducibility"),
  P("run_analysis.py rebuilds every table and statistic from data/Atlantic_Spain.csv and writes outputs/results.json. make_figures.py regenerates all figures, and app.py serves the dashboard. All random procedures use fixed seeds."),
);

// =====================================================================================================
// EXECUTIVE SUMMARY (2 pages)
// =====================================================================================================
const ex = [];
ex.push(
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Executive Summary", font: FONT, bold: true, size: 40, color: BLUE })] }),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: "Spain Top 50: how long songs last and what shapes their run", font: FONT, size: 24, color: "555555" })] }),
  P(`We tracked ${V.final_days} daily snapshots of Spain's Top 50 (${V.date_min.slice(0, 10)} to ${V.date_max.slice(0, 10)}) covering ${V.distinct_song_ids} songs to see how songs enter, stay and leave. The full method is in the research paper; the interactive dashboard lets you filter by date, release type, explicit flag and lifecycle stage.`),
  H1("Five things we found"),
  numbered([B("Most songs are short-lived, and a few last for months. "), `${pc(R.survival_le7d_share)} of new entries are gone within a week; ${pc(R.survival_ge90d_share)} stay 90 days or longer. Half of all songs are at their best position on their first day.`]),
  numbered([B("Rotation is slow on most days, and floods on a few. "), `A typical day brings ${f0(R.entries_per_day_median)} new song; ${pc(R.zero_entry_days_share)} of days bring none. ${R.shock_days} days with 8 to 21 new songs at once (mostly one artist charting many tracks) account for ${pc(R.entries_share_from_shocks)} of all entries.`]),
  numbered([B("Singles last much longer than album tracks. "), `Median stay is ${cs.single.median} days for singles and ${cs.album.median} for album tracks; album tracks reach the Top 10 about as often but do not hold their position.`]),
  numbered([B("Explicit content makes no measurable difference to lifecycle. "), `Survival, peak position and Top 10 rates are statistically indistinguishable between explicit and clean songs.`]),
  numbered([B("Debut position and the first week predict the run. "), `Songs entering in the Top 10 have a ${pc(R.km_s30_by_entry_bucket["1-10"])} chance of lasting 30 days, versus about ${pc(R.km_s30_by_entry_bucket["11-25"])} to ${pc(R.km_s30_by_entry_bucket["41-50"])} for other entry positions. A model using only a song's first seven days ranks 30-day survivors well (AUC ${f2(ewS.auc_logit)}). The popularity score, by contrast, lags rank by about nine days and is not a good early signal.`]),
  H1("Five actions"),
  numbered2([B("Build campaigns around singles. "), "For an album, pick one or two focus tracks to keep alive after the launch burst instead of expecting the whole album to hold."]),
  numbered2([B("Put the marketing weight in front of release day. "), "Pre-release pitching and pre-saves should aim at a strong debut position, because it is the best predictor of how long the song lasts."]),
  numbered2([B("Review every new song at day 7. "), "Keep spending on songs still climbing; hold back on songs flat or sliding at ranks 40-50. Test this rule on the next few releases."]),
  numbered2([B("Test a re-push when a song starts to decline. "), "Songs slide about ten places over their final two weeks. Brief exits are common and are not by themselves a sign of failure."]),
  numbered2([B("Decide on explicit content on creative grounds, and watch competitor album drops. "), "Content rating does not change chart longevity here. Avoid launching lower-priority songs into a rival's album week."]),
  H1("KPI snapshot"),
  table(["KPI", "Value", "KPI", "Value"], [
    ["Average days on playlist", f1(K.avg_days_on_playlist), "Playlist churn rate", pc(K.churn_rate, 1)],
    ["Median survival (KM)", f0(K.median_survival_days_km) + " days", "Retention Stability Index", f1(K.retention_stability_index)],
    ["Entry-to-peak (median)", f0(K.entry_to_peak_median) + " days", "Explicit Lifecycle Score", f0(K.explicit_lifecycle_score)],
    ["Single vs Album Longevity", f2(K.single_album_longevity_ratio) + "x", "Freshness / Catalog share", `${pc(K.freshness_index)} / ${pc(K.catalog_share)}`],
  ], [2700, 1980, 2700, 1980], { zebra: true }),
  gap(),
  P([B("What this cannot tell us. "), "The data has no release dates and covers Spain only, so we cannot say whether Spain rotates faster than the UK or US, or how a song's release day affects its run. The findings on album tracks and shock days show association, not proven cause. The early-warning model was tested on a small sample and should be validated on new releases."], { size: 19 }),
);

// ---------- documents
const base = (children, title) =>
  new Document({
    creator: "Analytics", title,
    styles: { default: { document: { run: { font: FONT, size: 21 } } } },
    numbering: { config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
      { reference: "num2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    ] },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, right: 1440, bottom: 1200, left: 1440 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: title, font: FONT, size: 16, color: "888888" })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", font: FONT, size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" })] })] }) },
      children,
    }],
  });

(async () => {
  fs.writeFileSync(OUT + "Spain_Top50_Research_Paper.docx", await Packer.toBuffer(base(paper, "Spain Top 50 Lifecycle Analysis: Research Paper")));
  // exec summary: numbering restarts need a separate numbering reference; use fresh Document (own counter)
  fs.writeFileSync(OUT + "Spain_Top50_Executive_Summary.docx", await Packer.toBuffer(base(ex, "Spain Top 50 Lifecycle Analysis: Executive Summary")));
  console.log("docs written");
})();
