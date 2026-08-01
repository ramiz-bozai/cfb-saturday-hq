# Data dictionary

Every stat column in `cfb_silver` and `cfb_gold`: what it measures, which direction is good,
where the value comes from (CFBD vs Saturday HQ), how we calculate anything we invent, the range
it occupies in this data, and where it will mislead you.

Market terms (vig, spread, moneyline) are also covered in `docs/BETTING_101.md`. CFP automatic-
qualifier rules are in `docs/CFP_RULES.md`.

**Formulas last audited:** 2026-07-30 against the dbt gold models, `dbt/macros/cfb_metrics.sql`,
and `src/saturday_hq/{ml,projections,briefs,cfp_rules}.py`.

All ranges and correlations below were measured on the built tables (2015-2025, one row per
team-season at its final week) rather than taken from documentation, so they describe what is
really in your catalog.

---

## How to read this

| Tag | Meaning |
|---|---|
| **CFBD** | Comes from a CollegeFootballData API field (after normalize / dedupe) |
| **Ours** | Invented or heavily transformed by Saturday HQ — see the formula |
| **Hybrid** | Prefer CFBD when present; otherwise compute |
| **Display only** | App coloring / wording — does not change stored numbers |

Silver generally **normalizes and deduplicates** CFBD (conference spellings, latest ingest wins).
Those transforms change which quote/row you see, but they do not invent new sports metrics.
Material exceptions are called out (portal filters, game outcomes, de-vig).

---

## Three conventions that explain most of the column names

**1. Not every stat is better when it is higher.** Defensive ratings measure what a team allows,
so lower wins. Measured against final win percentage:

| column | correlation with win% | direction |
|---|---|---|
| `sp_overall` | +0.796 | higher is better |
| `sp_offense` | +0.658 | higher is better |
| `sp_defense` | **-0.643** | **lower is better** |
| `sp_special_teams` | +0.258 | higher is better |
| `ppa_offense` | +0.645 | higher is better |
| `ppa_defense` | **-0.600** | **lower is better** |
| `talent` | +0.301 | higher is better |
| `recruiting_points` | +0.333 | higher is better |
| `sp_rank` | -0.782 | lower is better (1 = best) |

**2. A `_prior` suffix means last season's value.** Unsuffixed SP+ and PPA are *this* season's
ratings. CFBD computes them from the whole season, so for a completed game they already
incorporate its result — fine for answering "how good was this team in 2019", disqualifying as a
model input. The `_prior` columns hold last season's ratings, which are knowable before kickoff
and are what the model trains on.

**3. An `_fbs` suffix means non-FBS opponents were excluded.** Most teams schedule one or two FCS
opponents and win by roughly twice their usual margin. The unsuffixed form columns are the
literal record; the `_fbs` versions are the comparable ones, and are what the model uses.

---

## SP+ (`sp_*`) — CFBD

SP+ is Bill Connelly's opponent-adjusted, tempo-free efficiency rating, published through CFBD.
Its unit is **points**, which makes it the most directly interpretable rating here: it answers
"how many points better than average is this team", not "what percentile is this team".

| column | meaning | range in this data | median |
|---|---|---|---|
| `sp_overall` | Net points per game against an average opponent | -36.6 to +36.3 | 1.5 |
| `sp_offense` | Adjusted points this offense would score per game | 6.0 to 54.0 | 28.5 |
| `sp_defense` | Adjusted points this defense would allow per game | 3.7 to 51.9 | 27.3 |
| `sp_special_teams` | Points of special-teams value per game | -3.1 to +3.3 | 0.1 |
| `sp_rank` | Rank by `sp_overall`, 1 = best | 1 to 136 | — |
| `sp_sos` | Schedule strength as a win probability (see below) | 0.750 to 0.985 | 0.907 |

**The components add up.** `sp_overall` = `sp_offense` − `sp_defense` + `sp_special_teams`, exactly.
Across all 1,437 team-seasons the largest deviation is 0.1 points, which is rounding.

**`sp_overall` really is a scoring margin.** It correlates +0.862 with a team's actual average
margin, so reading "+14" as "about two touchdowns better than an average team per game" is fair.

`sp_offense` and `sp_defense` are absolute adjusted scoring rates, not differences from average —
a median offense sits near 28.5 points. An offense at 40 is elite; a defense at 40 is being carved up.

### `sp_sos` runs backwards from most people's intuition

Higher means an **easier** schedule, not a harder one. It reads as the win rate a strong team
would be expected to post against this slate. Group of Six teams average 0.932 while Power 4
teams average 0.851; Notre Dame sits at 0.855.

Do not read its raw correlation with winning (−0.163) as evidence of direction — G6 teams have
the easiest schedules *and* the worst records because they are weaker teams.

**`sp_sos` is only populated for 2015-2018.** Null from 2019 onward. Nothing depends on it.

### `sp_second_order_wins` (silver only)

Wins a team's per-drive efficiency says it *should* have had. Gap vs actual wins ≈ luck proxy.
In `cfb_silver.sp_plus` only; not carried into gold.

---

## PPA (`ppa_*`) — CFBD

Predicted Points Added is CFBD's expected-points model (play-level counterpart to SP+).

| column | meaning | range | median |
|---|---|---|---|
| `ppa_offense` | Expected points added per offensive play | -0.11 to 0.50 | 0.18 |
| `ppa_defense` | Expected points added *allowed* per play — lower is better | -0.11 to 0.54 | 0.16 |
| `ppa_offense_passing` / `ppa_offense_rushing` | Split by play type | — | — |
| `ppa_defense_passing` / `ppa_defense_rushing` | Allowed, split by play type | — | — |

Per-play scale: a median offense at 0.18 is roughly 12–13 points of offense over a 70-play game.
PPA and SP+ are **not** on the same scale — never difference them against each other.

Season averages as published are **not** opponent-adjusted the way SP+ is. When they disagree,
SP+ is the more schedule-aware of the pair.

---

## Talent and recruiting — CFBD

| column | meaning | range | median |
|---|---|---|---|
| `talent` | 247Sports composite team talent — ratings of players currently on the roster | 0 to 1018 | 574 |
| `recruiting_points` | Composite score of that season's incoming class | 9.5 to 333 | 171 |
| `recruiting_rank` | Rank of that class, 1 = best | — | — |

`talent` is accumulated (several recruiting cycles); `recruiting_points` is one signing class.
Both are known before the season starts, which is why `talent_diff` is a legitimate model feature
while same-season SP+ is not.

### `talent = 0` is a real value

**Air Force, Army, and Navy carry a hard `0`** from 2022 onward (gradual decline, not a feed cliff).
Treat `0` as the bottom of the scale, not missing. **Actual gap:** Air Force and Navy are null for
2025 — median imputation during training asserts roughly even talent for two of the least-rated
rosters in FBS. Known and accepted (`DECISIONS.md`).

---

## Rankings (`cfb_silver.rankings`) — CFBD

| column | meaning |
|---|---|
| `poll` | AP Top 25, Coaches Poll, or CFP rankings |
| `rank` | Position in that poll, 1 = best |
| `points` | Voting points received |
| `first_place_votes` | Count of first-place votes |

Grain is season × week × poll × team — filter to one `poll` before aggregating. Ingested but not
surfaced in gold; the playoff simulator uses `preseason_rank` from its own composite as a
stand-in rather than a poll.

---

## Form and record (`cfb_gold.team_week`) — Ours

One row per team per week, holding that team's record **cumulative through that week**.
**Source of truth:** `gold_team_week` (built from completed games + season FBS membership).

| column | formula / meaning |
|---|---|
| `games_played`, `wins`, `point_diff` | Cumulative through each game, ordered by `(start_date, game_id)` |
| `losses` | `games_played − wins` |
| `win_pct` | `wins / games_played` |
| `avg_margin_l3` | Mean margin over current + prior 2 games (**includes FCS**) |
| `fbs_games_played`, `fbs_wins`, `win_pct_fbs` | Same cumulatives, **FBS opponents only** |
| `avg_margin_l3_fbs` | Rolling mean margin over the latest 3 **FBS** games — not “FBS among last three all-opp games” |
| `won` | `points_for > points_against` (ties = false) |
| `points_for`, `points_against`, `opponent`, `is_home` | That week's individual game |
| `sp_*_prior`, `ppa_*_prior` | Same team at `season − 1` |
| `conference` | Conference **as of that season** (historical, not current realignment) |
| `conference_group` | Power4 / G6 / Independent (Notre Dame) / Other |

Silver helpers: `home_won`, `margin_home`, `total_points` only on completed games with both
scores; `is_fbs_game` if at least one participant is FBS.

### Leakage traps

**A week-W row includes week W's game.** Joining on `week <= game_week` leaks the result.
`gold_game_features` joins the latest `team_week` with `start_date` **strictly before** kickoff;
a test enforces it.

**`conference` is historical.** A 2016 Oregon row reads Pac-12, not Big Ten.

### Game features (`gold_game_features`)

Home/away prefixes plus diffs: `sp_overall_diff`, `ppa_*_diff`, `talent_diff`, and `_prior`
variants. A `*_diff` is always **home − away** (for defense, lower is better, so a negative
difference favors the home team). FBS-vs-FBS games only.

---

## Market and betting columns

Posted prices are **CFBD**; implied / de-vigged probabilities are **Ours**.
**Source of truth:** `dbt/macros/cfb_metrics.sql` → `gold_game_features` → `gold_matchup_card`.

None are model inputs — `FEATURE_COLS` excludes them so model-versus-market stays meaningful.

| column | origin | meaning |
|---|---|---|
| `market_spread` | CFBD | Closing spread, **home perspective** (negative = home favored) |
| `market_spread_open` | CFBD | Opening spread |
| `market_ou` / `market_ou_open` | CFBD | Closing / opening total |
| `market_home_ml`, `market_away_ml` | CFBD | American moneylines |
| `market_home_win_prob_implied` | Ours | Raw implied win % from home ML |
| `market_home_win_prob_novig` | Ours | De-vigged home win % |
| `line_provider` / `opening_line_provider` / `moneyline_provider` | Ours selection | Which book won each complete quote |

### Formulas

American ML → implied probability:

- ML &lt; 0: `(-ML) / ((-ML) + 100)`
- ML ≥ 0: `100 / (ML + 100)`

De-vig: `p_home_raw / (p_home_raw + p_away_raw)`. Null if either price is missing. Both sides must
come from the **same** book (`silver_moneylines`).

Sportsbook priority: Consensus → DraftKings → Bovada → ESPN Bet → Caesars → other. Each silver
market table keeps only **complete** rows for its contract, then applies that priority.

### Interpretation

In this data implied probs sum to ~**1.044** (house cut). Raw home averages 0.588 vs de-vigged
0.563. Use **novig** for any comparison with the model.

`market_spread` correlates −0.661 with actual home margin; average spread −4.1 vs average home
margin +4.03; favorites win 73.7% of the time.

Moneylines: 3,771 / 8,326 FBS-vs-FBS games (45%); none 2015–2020; 91–98% per season from 2021.
Model-versus-market is a recent-seasons analysis.

See `docs/BETTING_101.md` for vig / de-vigging pedagogy.

---

## Matchup model and briefs — Ours

**Source of truth:** `src/saturday_hq/ml/train.py`, `gold_matchup_card`, `briefs/generate.py`

| column | where | meaning |
|---|---|---|
| `model_home_win_prob` | `game_predictions`, `matchup_card` | Logistic `predict_proba` that home wins |
| `model_version` / `scored_at` | same | Which registered model / when scored |
| `model_minus_market_home` | `matchup_card` | `model_home_win_prob − market_home_win_prob_novig` |

`model_minus_market_home` is a **disagreement, not an edge**. On holdout data the market is more
accurate.

### Pipeline

1. Median impute features  
2. Z-standardize  
3. Balanced logistic regression (`max_iter=1000`, `class_weight="balanced"`)

### Features (all from `gold_game_features`; **no lines**)

- Prior-season SP+/PPA diffs and home/away components  
- Current-season `talent_diff`  
- FBS-only form: `win_pct_fbs`, `avg_margin_l3_fbs` (home and away)  
- `neutral_site`

Holdout metrics (Brier, log loss, AUC, accuracy) land in `cfb_ml.train_summary` / MLflow.
Leakage tripwire: `scripts/feature_audit.py` warns if model AUC beats de-vigged market AUC by
more than **0.05**.

### Weekly briefs (`cfb_gold.weekly_brief`)

One row per `game_id + team`. Away rows **flip** home values (`1 − p`, negated spread and
model−market). No new predictive metric — presentation plus prose. `WEEK = None` refreshes all
weeks in the requested season/type and preserves other history.

---

## Preseason ratings and playoff projections — Ours

**Source of truth:** `src/saturday_hq/projections/simulator.py`, `cfp_rules.py`

### `preseason_team_ratings.rating`

Inputs: **prior** SP+/PPA, **current** talent (fallback prior). Z-score each column across FBS,
then:

```
0.45 × z(sp_overall)
+ 0.20 × z(sp_offense)
+ 0.15 × (−z(sp_defense))
+ 0.10 × z(ppa_offense)
+ 0.05 × (−z(ppa_defense))
+ 0.05 × z(talent)
```

Missing z’s contribute 0. `preseason_rank` = min-rank of `rating` descending.
`rating` is in standard deviations, not SP+ points.

**Naming trap:** `sp_overall` / `ppa_*` on this table are prior-season inputs despite unsuffixed
names.

### Monte Carlo (`season_projections` / `playoff_projections`)

- Completed games → observed wins  
- Remaining games → Bernoulli from `model_home_win_prob` when present  
- Else: `1 / (1 + exp(−1.1 × rating_diff))`, with **+0.30** home rating boost if not neutral  
  (~58% home when ratings are equal; historical FBS home win rates ~57–60%). Fallback only —  
  the trained matchup model uses its own `neutral_site` feature.  
- Conference champ proxy = conference wins, then rating  
- Each sim applies published 2026 CFP AQ rules (`docs/CFP_RULES.md`) on the sim ranking  

Written: `mean_wins`, `median_wins`, `win_total_p10` / `p90`, `playoff_odds`, `avg_seed_if_in`,
`n_sims`.

---

## Season Preview metrics — Ours

These power the Season Preview. Core grain is player / unit / team for a target season, usually
with **prior-season** production attached to a constructed or published roster.

### Player production and usage (`gold_player_season`)

**Defense production score** (DL / LB / DB only):

```
tackles + 2×(TFL − sacks) + 3×sacks + 2×INT
```

CFBD/NCAA TFL includes sacks, so non-sack TFLs and sacks are weighted separately (equivalent to
`tackles + 2×TFL + sacks + 2×INT` when TFL ≥ sacks). Missing components = 0. Rough scale: ~15
rotational/impact floor, ~40–80 solid starter, 100+ elite.

**`usage_overall` (hybrid)**

1. Prefer CFBD offensive `usage.overall`  
2. Else DL/LB/DB: `defense_prod / team_defense_prod`  
3. Else null (typical OL / ST)  

Defense “usage” in the App is **not snap %** — it is share of team tackle-weighted production.

**`production_score` (hybrid)** — first non-null of:

1. CFBD `total_ppa_all`  
2. CFBD `usage_overall × 50`  
3. `defense_prod` for DL/LB/DB  
4. `0`  

Offense (PPA) and defense (tackle index) are **different units** — do not equate a WR’s score to
a DT’s without that caveat.

**`talent_score`:** recruiting rating, else `stars / 5`, else null.

**Position groups:** CFBD strings → `QB`, `RB`, `WR/TE`, `OL`, `DL`, `LB`, `DB`, `ST`, `OTHER`
(`dbt/macros/position_group.sql`).

### Portal moves (`gold_portal_moves`)

Silver keeps only moves with a **destination** and drops `eligibility = Withdrawn` — metrics
describe **committed transfers**, not every portal entry.

Prior stats join at origin team for season `S − 1` (athlete ID via origin roster name key).

| Label | Skill / defense (with prior stats) | OL / special teams | Missing prior stats |
|---|---|---|---|
| `impact` | usage ≥ 0.15 **or** production ≥ 15 | talent ≥ 0.85 **or** stars ≥ 4 | talent ≥ 0.90 **or** stars ≥ 4, else see below |
| `depth` | Otherwise (when prior exists) | Rated but below impact | Rated but below that high bar |
| `unknown` | — | No talent/stars | No prior and no talent/stars |
| `projected_starter` | usage ≥ 0.25 **or** production ≥ 40; **RB / WR/TE also** if talent ≥ 0.85 **and** (production ≥ 10 **or** usage ≥ 0.08) | talent ≥ 0.90 **or** stars ≥ 4 | talent ≥ 0.90 **or** stars ≥ 4 (RB/WR/TE use the talent+role floor above) |

**Comparable production:** QB/RB/WR-TE share a PPA-based scale (e.g. lost a 60 WR, gained a 30 RB).
DL/LB/DB share a tackle-based scale. Do **not** compare a WR’s production number to a LB’s.
OL/ST use talent, not production.

Offense ledger net production = QB + RB + WR/TE only (OL excluded; use net talent).

### Constructed rosters (`gold_roster_snapshot`)

If CFBD has not published the season roster: prior roster − portal/draft exits + portal arrivals;
`roster_source = constructed` (else `published`). `prior_*` columns are always prior-season stats.

### Returning production — team (`gold_returning_production_team`)

**Prior production retained:** share of last season’s production still on the roster via
non-transfer players. Portal arrivals are **not** in the denominator (see transfer dependency /
net flows for replacement).

**CFBD path:** `/player/returning` is used only when the team has a **published** roster for the
target season **and** CFBD published a same-season returning row. Constructed rosters always use
the computed path.

Lead fan metrics: `percent_offense_returning`, `percent_defense_returning`. Overall
`percent_production` is secondary. Offense = returning yards / prior yards; defense = returning
defense production score / prior.

### Unit continuity (`gold_unit_continuity`)

One row per team × position group × season.

**Returning shares**

- Production % / usage %: null for OL/ST (no CFBD signal; UI shows —). Else returning /
  prior group production (or usage), with headcount fallback when prior is empty.
  **Clamped to [0, 1]** when present — signed production can otherwise exceed 100% when
  portal departures are net-negative.

**`continuity_score` (0–100)**

| Condition | Score |
|---|---|
| Usage &gt; 0.05 and production &gt; 1 | `100 × (0.6 × usage_ret + 0.4 × prod_ret)` |
| Usage only | `100 × usage_ret` |
| Production only (typical DL/LB/DB) | `100 × prod_ret` |
| Neither (typical OL/ST) | `100 × headcount retention` |

**Net flows**

| Metric | Formula |
|---|---|
| `net_production_gained` | Σ prior production in − Σ prior production out (portal + non-duplicated draft) — **unit-scoped**; do not sum across offense and defense for fan display |
| `net_offense_production_gained` / `net_defense_production_gained` | Team ledger: offense = QB/RB/WR-TE only; defense = DL/LB/DB (OL on talent axis) |
| `talent_added` / `talent_lost` | **Average** talent of inbound / outbound (not a sum) |
| `net_talent_gained` | `avg(in) − avg(out)`; null only if both missing |
| `net_talent_proxy` | Avg transfer stars − avg returning stars |

**`replacement_risk`**

| Label | Rule |
|---|---|
| `high` | Departed production &gt; 0 and returning &lt; 30% of departed |
| `elevated` | ≥1 impact loss and 0 impact additions |
| `manageable` | Otherwise |

### Portal team ledger (`gold_portal_team_ledger`)

Team rollup of unit counts. `avg_continuity_score` = **mean** across position groups (not
roster-weighted). Team `net_talent_gained` uses the same average-in − average-out rule.

Fan-facing production nets are **split by side** (`net_offense_production_gained`,
`net_defense_production_gained`) because offense uses PPA-based production and defense uses the
tackle-weighted index. `net_production_gained` (all units summed) is kept for debugging only —
do not show it as one comparable currency.

### Transfer dependency (`gold_transfer_dependency`)

Overall plus offense (QB/RB/WR-TE) and defense (DL/LB/DB).

`pct_usage_from_transfers` = transfer prior usage / all prior usage (fallback: production share).

`transfer_dependency_score` (0–100), higher = more risk:

```
100 × (
  0.45 × transfer_usage_or_production_share
+ 0.25 × min(1, critical_units_on_transfers / 4)
+ 0.20 × min(1, transfer_projected_starters / 5)
+ 0.10 × min(1, avg_transfer_prior_production / 40)
)
```

Critical unit = `replacement_risk` in (`high`, `elevated`) **and** the unit added impact transfers.
`pct_departed_production_replaced` = `min(1, added / departed)`.

### Replacement risk callouts (`gold_replacement_risk`)

FBS only (target or prior season in `silver_team_seasons`), same gate as other Season Preview
team marts. Surfaces high/elevated risk, continuity ≤ 40, or departed share ≥ 40%. Unit-specific
“what left” metric: QB pass att; WR/TE rec yds; RB rush yds; DL sacks; LB tackles; DB INTs if
prior group INTs ≥ 2 else tackles; ST kick points; OL/other production score.
`departed_share` = departed / prior. Best returner ranked with a unit-specific stat (DB:
`10×INT + tackles`). When the unit has no non-transfer players left, `best_returner` is null and
the callout ends with `; no returning production at this unit`.

### QB room (`gold_qb_room`)

| Metric | Formula |
|---|---|
| `career_avg_ppa_weighted` | `Σ(avg_ppa × pass_att) / Σ(pass_att)` |
| `int_rate` / `turnover_rate` | INTs / att; (INTs + fumbles lost) / att |
| `rush_share_proxy` | Rush att / (rush + pass att) |

**Returning starter:** non-transfer, top returning QB, and (≥200 prior att) or (≥100 att and
≥50% of prior team pass attempts).

**`qb_class`** (first match): Proven elite (≥250 att, PPA ≥ 0.35) → Proven average (≥150) →
High-upside transfer (≥100 att or ≥4★) → Experienced but limited (≥100 att, PPA &lt; 0.10) →
Major uncertainty (no proven returners, no transfer QBs, max prior att &lt; 50) → Unproven
competition.

FBS only (target or prior season in `silver_team_seasons`), same gate as other Season Preview
team marts.

`room_class` = team priority rollup. Proven returner count: non-transfer with ≥150 career/prior att.

### App display bands — Display only

`app/client/src/labels.ts` (does not change stored numbers):

| Helper | Bands |
|---|---|
| Continuity / returning % | ≥70 Strong, ≥40 Mixed, else Thin |
| Transfer dependency | ≥70 Heavy, ≥40 Moderate, else Light |
| Net production | &gt;5 Gained, &lt;−5 Lost, else Even |
| Net talent | &gt;0.02 Gained, &lt;−0.02 Lost, else Even — **portal only** (not HS class) |
| HS class (Season Preview UI) | From gold `hs_recruiting_class` (CFBD `/recruiting/players`). **247Sports** stars and composite ratings via CollegeFootballData. Team score / national rank = **average 247Sports `rating`** among rated signees (≥10 rated). Display: `#rank · avg stars`. Separate from portal `net_talent_gained`. |
| Portal / transfer stars & ratings | CFBD `/player/portal` — **247Sports** transfer stars and transfer rating. |
| Talent score (portal / OL) | Coalesce: 247Sports transfer rating → HS recruiting rating → stars/5 (via CollegeFootballData). |


### Metric views (Genie)

| UC name | Grain | Role |
|---|---|---|
| `cfb_gold.mv_season_preview_team` | team × season | Returning %, transfer dependency, portal ledger |
| `cfb_gold.mv_unit_continuity` | team × position_group × season | Continuity score, unit flows, departed share |

Built by dbt (`materialized='metric_view'`). Query with `MEASURE(...)`, e.g.
`SELECT team, MEASURE(transfer_dependency_score) FROM cfb_gold.mv_season_preview_team WHERE season = 2026 GROUP BY team`.

---

## Identity and outcome columns

| column | origin | meaning |
|---|---|---|
| `game_id` | CFBD | Unique game id |
| `season` | CFBD | Year the season kicked off (January bowls belong to prior year) |
| `week` / `season_type` | CFBD | Week within regular or postseason |
| `completed` / `neutral_site` / `conference_game` | CFBD | Status flags |
| `margin_home` / `total_points` / `home_won` | Ours | Completed-game outcomes |
| `is_fbs_game` | Ours | ≥1 FBS participant |
| `home_feature_week` / `away_feature_*` | Ours | As-of form provenance for features |
| `is_fbs` / `is_notre_dame` | Ours flags | Membership / Notre Dame special case |
| `_source_path`, `_ingest_mode` | Ours | Landing-file lineage |

---

## Coverage gaps, in one place

| what | gap |
|---|---|
| `sp_sos` | 2015–2018 only; null from 2019 |
| `sp_special_teams` | Missing for 2020 and 2021 |
| `sp_overall` | Two teams missing in 2017 |
| `talent` | Air Force and Navy null in 2025; `0`s from 2022 are genuine |
| Moneylines | 45% of FBS-vs-FBS; none 2015–2020 |
| `_prior` ratings | All 765 games of 2015; plus FCS promotees each year |
| Form columns | Null week 1 (~902 games) and ~100 more before first FBS game; training imputes |
| 2020 season | COVID — thinner schedule |

---

## Source index (calculated metrics)

| Domain | Primary code |
|---|---|
| Market / de-vig | `dbt/macros/cfb_metrics.sql`, `gold_game_features`, `gold_matchup_card` |
| Form / features | `gold_team_week`, `gold_game_features` |
| Player production | `gold_player_season`, `defense_production_score` |
| Portal / roster | `silver_player_portal`, `gold_portal_moves`, `gold_roster_snapshot` |
| Continuity / ledger | `gold_unit_continuity`, `gold_portal_team_ledger`, `gold_returning_production_team` |
| Transfer dependency | `gold_transfer_dependency` |
| Replacement / QB | `gold_replacement_risk`, `gold_qb_room` |
| Season Preview metric views | `mv_season_preview_team`, `mv_unit_continuity` |
| Matchup model | `src/saturday_hq/ml/train.py` |
| Projections / CFP | `src/saturday_hq/projections/simulator.py`, `cfp_rules.py` |
| Briefs | `src/saturday_hq/briefs/generate.py` |
| UI bands | `app/client/src/labels.ts` |
