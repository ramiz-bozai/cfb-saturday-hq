# Saturday HQ — Locked Decisions

| Decision | Choice |
|---|---|
| Scope | FBS only |
| History | 2015 onward |
| Primary metrics | SP+ and PPA (first-class) |
| Betting lines | Include in UI as **Model vs market** (not betting advice) |
| Model training | Train **without** line as a feature so model-vs-market is meaningful |
| Play-by-play | Out of scope for v1 |
| Audience | Demo-able / clean |
| Historical load | Download files into a Unity Catalog **Volume**, then load bronze from Volume |
| Transformation layer | **dbt** for bronze → silver → gold; Python only for ingest, ML, projections, briefs |
| Bronze ingestion | dbt models over `read_files()` on the Volume (no Python bronze loader) |
| Tool handoffs | Exactly one each way: Python ingest → dbt → Python scoring/serving. `matchup_card` is a dbt **view** so nothing in dbt runs after scoring |
| Where dbt runs | Job **dbt tasks**, never from a notebook, against a committed `dbt/profiles.yml`. No `warehouse_id` on the task, so Databricks injects `DBT_ACCESS_TOKEN` for the Run As principal; `.env` supplies it locally |
| Environments | `cfb_saturday_hq_dev` and `cfb_saturday_hq_prod` each hold a full bronze → silver → gold. Selected by `SATURDAY_HQ_ENV` (Python) and `--target` (dbt), both from the bundle target |
| Raw data | One shared volume in `cfb_saturday_hq_raw.landing`, outside both environments: the CFBD API is called once and dev reads exactly what prod reads. Bronze is still per-environment, because it is code output |
| Model registry | Unity Catalog, `<catalog>.cfb_ml.matchup`, so the model follows the environment. Scored via the `production` alias, falling back to the newest version |
| Current season | Derived from the date with an August rollover; never edited between runs |
| Ratings vintage | Features use prior-season SP+/PPA (`_prior`). Same-season ratings are CFBD season aggregates, so for a finished game they encode its result. Honest cost: test-2025 Brier 0.148 to 0.205. Because bronze retains every dated file, the weekly job is accumulating in-season snapshots, so a true as-of rating becomes possible for 2026+ without new ingestion |
| Market probability | `market_home_win_prob_novig` de-vigs against the away price and is what `model_minus_market_home` uses. The raw implied column stays for display. The 4.5% overround was inflating the home side by 2.5 points on every game, biasing every model-vs-market comparison one way |
| Leakage tripwire | `scripts/feature_audit.py` refits FEATURE_COLS locally and warns when holdout AUC beats the sportsbook's by more than 0.05. Cheap enough to run before every training job |
| Feature as-of cutoff | Form joins `team_week` on `week < game week`, exclusive. A team_week row is cumulative through its own week, so the previous inclusive join fed the model the outcome it was predicting — fake holdout accuracy of 88% vs 78% once corrected. Guarded by `gold_game_features_form_precedes_game` |
| Team dimension | `silver_team_seasons` (season-grained) for anything historical; `silver_teams` stays current-only for "who is FBS now". Conference realignment mislabeled ~22% of teams per season for 2015-2022 when current membership was applied retroactively |
| Form features | Model uses `win_pct_fbs` / `avg_margin_l3_fbs`, which exclude non-FBS opponents (margins there average ~2x). The unsuffixed columns remain the literal record for reporting |
| Ongoing refresh | CFBD **API** weekly (Monday), plus a lines-only pull on Friday |
| Refresh cadence | Games are weekly and every model input moves only after they are played, so a daily pull spent ~13 calls a day for nothing. Monday 10:00 ET captures the full weekend |
| CFBD call budget | Domains are tiered by how often they change (static / season-static / weekly / market), the API is skipped outside August–January, and postseason endpoints are skipped until December. Steady state is 7-9 calls a week instead of ~91 |
| Refresh SLA | Daily |
| CFP logic | Published 2026 12-team rules; model ranking is a stand-in for committee rank |

## Disclaimers (show in App + Dashboards)

1. For analysis and entertainment only. Not gambling advice.
2. Playoff projections use Saturday HQ ratings + published CFP structure. Not an official CFP selection.
