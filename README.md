# 🎧 Spain Top 50: Content Maturity, Release Lifecycle & Playlist Rotation Analysis

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](http://localhost:8503)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Research: Atlantic Records](https://img.shields.io/badge/Client-Atlantic%20Recording%20Corp-blue)](https://www.atlanticrecords.com/)

An empirical music streaming intelligence and lifecycle velocity suite built for **Atlantic Recording Corporation** and **Unified Mentor**. Analyzes **555 consecutive daily snapshots** of Spain's Top 50 playlist (27,800 observations) to optimize release pacing, catalog monetization, and playlist retention strategies.

---

## 🌟 Executive Summary & Key Empirical Findings

1. **Low Routine Churn vs. Extreme "Shock-Day" Volatility:**
   - Routine baseline churn is just **3.1% daily** (1.57 new songs/day), with **41.1% of days seeing 0 new entries**.
   - However, **20 "Shock Days"** ($\ge 8$ new entries/day) account for **32.5% of all chart entries**, driven by monolithic album drops (e.g., Bad Bunny, Saiko, Quevedo, Mora, Rauw Alejandro).
2. **Singles Drastically Outlast Album Tracks (2.30x Longevity Advantage):**
   - Standalone singles survive a median of **30 days** on the chart vs. only **10 days for album tracks** (Log-rank test $p < 0.001$, Cliff's $\delta = +0.265$). Album cuts suffer an acute 75% exit rate within 7 days.
3. **Explicit Content Parity:**
   - Explicit tracks account for **59.9% of songs** and **61.9% of chart slot-days**, yet show **zero survival penalty** compared to clean tracks (Log-rank $p = 0.744$, Explicit Lifecycle Score = **101**).
4. **Day-1 Peak Supremacy:**
   - **50.5% of songs achieve their peak rank on their first day of entry**.
5. **Catalog Dominance:**
   - **57.7% of Spain's Top 50 chart capacity is occupied by catalog tracks (>90 days old)**, leaving only **21.7% for fresh releases ($\le 30$ days)**.
6. **Machine Learning Early-Warning Predictor (Day 7):**
   - Classifies 30-day survivors using only the first 7 days of performance with **0.78 ROC-AUC** (Gradient Boosting & Logistic Regression).

---

## 📊 Core Performance Indicators (KPIs)

| KPI Name | Metric Value | Parametric Formula | Market Benchmark & Validation |
|---|---|---|---|
| **Average Days on Playlist** | **36.1 days** (Med: 14.0 d) | $\bar{T} = \frac{1}{N} \sum T_i$ | 30–45 days; excludes Day-1 left-censored tracks. |
| **Median Survival (KM)** | **23.0 days** | $\hat{S}(t) = \prod (1 - d_i/n_i)$ | Censoring-adjusted Kaplan-Meier estimator. |
| **Entry-to-Peak Time** | **13.6 days** (Med: 0.0 d) | $\bar{\Delta} = \frac{1}{N} \sum (t_{pk} - t_{ent})$ | 50.5% peak immediately on Day 1. |
| **Playlist Churn Rate** | **3.1% daily** (1.57 songs/d) | $\bar{C} = \frac{1}{\|D\|} \sum \frac{\text{Entries}_d}{50}$ | 4 survey gap dates excluded from transition math. |
| **Retention Stability Index** | **41.5** | $\text{RSI} = 100 \times \frac{1 - \bar{C}}{1 + \text{CV}}$ | Reflects volatility from sporadic album shock drops. |
| **Explicit Lifecycle Score** | **101** | $\text{ELS} = 100 \times \text{Ratio}_{\text{exp/clean}}$ | Log-Rank $p = 0.744$, Mann-Whitney $p = 0.779$ (Parity). |
| **Single vs Album Longevity**| **2.30x** (Med: 3.00x) | $\text{Ratio} = \bar{T}_{single} / \bar{T}_{album}$ | Log-Rank $p < 0.001$, Cliff's $\delta = +0.265$. |
| **Freshness Index** | **21.7%** | $\text{FI} = \frac{1}{N} \sum \mathbb{I}(\text{Age} \le 30)$ | Evaluated post 90-day burn-in window. |
| **Catalog Share** | **57.7%** | $\text{CS} = \frac{1}{N} \sum \mathbb{I}(\text{Age} > 90)$ | Highlights stickiness of regional evergreen hits. |
| **Top 10 Turnover Rate** | **7.4% daily** | $\text{Turnover}_{10} = \frac{\|\Delta \text{Top10}\|}{10}$ | Top 10 churn is half that of positions 41–50. |

---

## 🎛️ Interactive Streamlit Dashboard

The production dashboard (`app.py`) features 11 modules:
- **📈 Executive Overview:** 10 real-time KPIs, dynamic takeaways, and interactive KPI Validation Guide with LaTeX equations.
- **🎧 Song Spotlight & Trajectory:** Spotify album artwork viewer, track metadata badges, and dual-axis rank vs. popularity trajectory.
- **🌊 Entry vs Exit Flows:** Daily flow trends, high-readability 3-stage migration funnel, and rank volatility gradient.
- **🔄 Lifecycle Stages:** Stage composition across 27,700 song-days and empirical next-day transition matrix.
- **⚖️ Content Maturity:** Kaplan-Meier survival curves, statistical significance tests, and duration/track-count retention analysis.
- **📉 Playlist Churn:** Daily churn time series, 7-day rolling trends, and top 10 shock day records.
- **⏳ Temporal & Period Comparisons:** Year-over-Year (2024 vs. 2025) shifts, quarterly dynamics, and release-day seasonality.
- **⭐ Popularity Dynamics:** API popularity lag analysis (empirical 9-day lag behind chart rank peaks).
- **🧬 Archetypes & Early Warning:** K-Means cluster validation ($s = 0.54, F = 142.6$) and interactive Day-7 survival probability scorer.
- **🎯 Actionable Recommendations:** 4 concrete operational playbooks for release pacing, shock defense, and catalog monetization.
- **📋 Data Quality & Audit:** Ingestion reports, missing dates handling, and censoring controls.

---

## 🚀 Quickstart & Installation

```bash
# 1. Clone repository
git clone https://github.com/Shloksharma-27/spain-top50-music-lifecycle-analysis.git
cd spain-top50-music-lifecycle-analysis

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run data analytics pipeline & figure generation
python run_analysis.py
python make_figures.py

# 5. Launch interactive dashboard
streamlit run app.py
```

---

## 📁 Repository Architecture

```
├── .streamlit/             # Streamlit dark theme configuration
├── data/                   # Raw & processed datasets
│   ├── Atlantic_Spain.csv  # 27,800 raw daily chart records
│   ├── daily_clean.csv     # Validated & normalized daily data
│   ├── lifecycle.csv       # Track-level aggregated lifecycle metrics
│   ├── song_day_stages.csv # Song-day velocity & stage classifications
│   └── archetypes.csv      # K-Means cluster assignments
├── outputs/
│   ├── figures/            # 12 publication-quality empirical figures (PNG)
│   ├── results.json        # Machine learning metrics & statistical test statistics
│   ├── Spain_Top50_Research_Paper.docx # Academic research paper in Word
│   ├── Spain_Top50_Research_Paper.md   # Research paper in Markdown
│   └── Spain_Top50_Executive_Summary.docx # Policy briefing paper
├── utils/
│   ├── pipeline.py         # Ingestion, normalization, stage classification
│   └── analytics.py        # KPI formulas, Kaplan-Meier curves, validation metadata
├── app.py                  # Streamlit analytics application
├── run_analysis.py         # Full statistical pipeline reproduction script
├── make_figures.py         # High-resolution figure rendering script
└── requirements.txt        # Python dependency manifest
```

---

## 📜 Strategic Recommendations for Atlantic Records

1. **Prioritize Staggered Singles over Monolithic Album Drops:** Singles deliver 2.3x greater longevity. Stagger 2–3 priority singles before releasing full projects.
2. **Day-7 Marketing Milestone Gate:** Utilize our 0.78 AUC model on Day 7. Extend spend if rank velocity is non-negative; cut ad spend if deteriorating below rank 40.
3. **Disregard Explicit Tag Penalties:** Explicit content achieves identical survival ($p = 0.744$). Do not sanitize creative output for Spain.
4. **Active Defense During Competitor Shock Drops:** Protect mid-tier tracks (ranks 35–48) with targeted boosts when major artists drop albums.
