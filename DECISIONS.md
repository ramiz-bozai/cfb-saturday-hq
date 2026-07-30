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
| Market quote grain | `silver_lines` guarantees one complete current spread/total quote; `silver_moneylines` guarantees a complete two-way pair from one provider; `silver_opening_lines` guarantees a complete opening spread/total quote. Gold left-joins all three and keeps separate provider columns. This prevents sparse Consensus rows from hiding real-book prices and never coalesces different books under one provider label |
| Weekly brief grain/history | One row per `game_id + team`, with explicit `season_type` because regular and postseason week numbers overlap. `WEEK = None` refreshes every week in the requested season/type. Delta `replaceWhere` updates only that scope, preserving every other season/type; a one-time schema migration reconstructs full history from `matchup_card` |
| Simulator optimization | **Parked.** The completed-conference replay still sits inside the simulation loop, invariant lookups are not vectorized, and completed seasons do not automatically short-circuit to one pass. Phase timings and 10% progress output are implemented now so the eventual optimization can be measured. Use `N_SIMS = 1` only for debugging or a finished season; production remains 2,000 |
| Leakage tripwire | `scripts/feature_audit.py` refits FEATURE_COLS locally and warns when holdout AUC beats the sportsbook's by more than 0.05. Cheap enough to run before every training job |
| Feature as-of cutoff | Form joins `team_week` on `feature start_date < game start_date`, exclusive. A team_week row is cumulative through its source game, so an inclusive join leaks the outcome being predicted. Timestamps also prevent postseason Week 1 from colliding with regular Week 1. The earlier inclusive week join produced fake holdout accuracy of 88% vs 78% once corrected. Guarded by `gold_game_features_form_precedes_game` |
| Team dimension | `silver_team_seasons` (season-grained) for anything historical; `silver_teams` stays current-only for "who is FBS now". Conference realignment mislabeled ~22% of teams per season for 2015-2022 when current membership was applied retroactively |
| Form features | Model uses `win_pct_fbs` / `avg_margin_l3_fbs`, which exclude non-FBS opponents (margins there average ~2x). The unsuffixed columns remain the literal record for reporting |
| Ongoing refresh | CFBD **API** weekly (Monday), plus a lines-only pull on Friday |
| Refresh cadence | Games are weekly and every model input moves only after they are played, so a daily pull spent ~13 calls a day for nothing. Monday 10:00 ET captures the full weekend |
| CFBD call budget | Domains are tiered by how often they change (static / season-static / weekly / market), the API is skipped outside August–January, and postseason endpoints are skipped until December. Steady state is 7-9 calls a week instead of ~91 |
| 2014 ratings backfill | **Passed on.** Would have cost 2 calls (`sp_plus`, `ppa_teams`) to give 2015's 765 games their `_prior` features. No regress risk — ratings are a dimension lookup joined on `season - 1`, so 2014 needs no prior season of its own — but 2015 is the one season with zero moneyline coverage, so it cannot contribute to model-vs-market either way. `history_start_year` stays 2015 and 2015 games train without prior ratings |
| Service academy talent | **Left as is.** The `0` for Air Force / Army / Navy from 2022 is a real value, not a gap: the decline is gradual (Navy 376 → 335 → 266 → 128 → 0) and Army still posts 17.3 in 2022 and 23.7 in 2025, whereas a dropped feed yields nulls. Nulling them would hand 125 games to the median imputer, which fills `talent_diff` with 8.7 ≈ "even talent" and moves home win probability by 14 points on average, up to 35, in the wrong direction. Accepted consequence: Air Force and Navy are genuinely null for 2025 and are median-imputed as average talent |
| Refresh SLA | Daily |
| CFP logic | Published 2026 12-team rules; model ranking is a stand-in for committee rank |

## Disclaimers (show in App + Dashboards)

1. For analysis and entertainment only. Not gambling advice.
2. Playoff projections use Saturday HQ ratings + published CFP structure. Not an official CFP selection.
