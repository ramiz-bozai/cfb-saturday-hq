# Data dictionary

Every stat column in `cfb_silver` and `cfb_gold`: what it measures, which direction is good, the
range it actually occupies in this data, and where it will mislead you.

All ranges and correlations below were measured on the built tables (2015-2025, one row per
team-season at its final week) rather than taken from documentation, so they describe what is
really in your catalog.

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

## SP+ (`sp_*`)

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

Two things make these numbers easier to reason about.

**The components add up.** `sp_overall` = `sp_offense` − `sp_defense` + `sp_special_teams`, exactly.
Across all 1,437 team-seasons the largest deviation is 0.1 points, which is rounding. So a team at
+10 overall got there some combination of scoring more and allowing less, and you can decompose it
without any extra data.

**`sp_overall` really is a scoring margin.** It correlates +0.862 with a team's actual average
margin, so reading "+14" as "about two touchdowns better than an average team per game" is fair.

`sp_offense` and `sp_defense` are absolute adjusted scoring rates, not differences from average —
a median offense sits near 28.5 points, which is roughly what teams actually score. An offense at
40 is elite; a defense at 40 is being carved up.

### `sp_sos` runs backwards from most people's intuition

Higher means an **easier** schedule, not a harder one. It reads as the win rate a strong team
would be expected to post against this slate, so a soft schedule pushes it toward 1.0. Group of
Six teams average 0.932 while Power 4 teams average 0.851, and Notre Dame, whose independent
schedule is deliberately brutal, sits at 0.855.

Do not read its raw correlation with winning (-0.163) as evidence of direction. That number is
confounded: G6 teams have the easiest schedules *and* the worst records, because they are weaker
teams. The conference comparison is the reliable signal.

**`sp_sos` is only populated for 2015-2018.** It is null from 2019 onward. Nothing depends on it.

### `sp_second_order_wins` (silver only)

The number of wins a team's per-drive efficiency says it *should* have had. The gap against actual
wins is the usual proxy for luck in close games. Available in `cfb_silver.sp_plus`; not carried
into gold.

---

## PPA (`ppa_*`)

Predicted Points Added is CFBD's expected-points model, and it is the play-level counterpart to
SP+. Each play moves a team's expected points up or down depending on down, distance, and field
position; PPA is the average of that movement.

| column | meaning | range | median |
|---|---|---|---|
| `ppa_offense` | Expected points added per offensive play | -0.11 to 0.50 | 0.18 |
| `ppa_defense` | Expected points added *allowed* per play — lower is better | -0.11 to 0.54 | 0.16 |
| `ppa_offense_passing` / `ppa_offense_rushing` | Same, split by play type | — | — |
| `ppa_defense_passing` / `ppa_defense_rushing` | Allowed, split by play type | — | — |

The scale is small because it is per play. A median offense at 0.18 gains a bit under two points
per ten plays, so across a 70-play game that is roughly 12-13 points of offense generated. The
passing and rushing splits are where PPA earns its keep: a team can be average overall while
being lopsided, and that shows up here in a way SP+ cannot show you.

The unit is points per play, so PPA and SP+ are **not** on the same scale and should never be
differenced against each other.

One caveat: these are season averages as published, without the opponent adjustment SP+ applies.
A team that played a soft schedule can post strong PPA on merit that would not survive
adjustment. When the two disagree, SP+ is the more schedule-aware of the pair.

---

## Talent and recruiting

| column | meaning | range | median |
|---|---|---|---|
| `talent` | 247Sports composite team talent — recruiting ratings of players currently on the roster | 0 to 1018 | 574 |
| `recruiting_points` | Composite score of that season's incoming class | 9.5 to 333 | 171 |
| `recruiting_rank` | Rank of that class, 1 = best | — | — |

The distinction matters: `talent` is accumulated (four or five recruiting cycles still on the
roster) while `recruiting_points` is one signing class. Talent is the better predictor of a
team's ceiling; a single strong class barely moves a roster.

Both are known before the season starts, which is why `talent_diff` is a legitimate model feature
while same-season SP+ is not.

### `talent = 0` means "no composite-rated recruits", and it is a real value

**Air Force, Army, and Navy carry a hard `0`** from 2022 onward. It is tempting to read this as a
coverage outage, but the history says otherwise: the decline is gradual rather than a cliff (Navy
runs 376, 335, 266, 128, then 0; Air Force 186, 152, 72, 30, then 0), and Army posts small
non-zero values of 17.3 in 2022 and 23.7 in 2025. A dropped feed produces nulls, not a tidy slide
into zero. These academies simply sign almost nobody the composite rates.

So treat `0` as the genuine bottom of the scale, not as missing. It is extreme against a median of
574, and it will dominate `talent_diff` in those games, but it is directionally true.

**The actual gap is elsewhere: Air Force and Navy are null for 2025.** Nulls get median-imputed
during training, which asserts roughly *even* talent for two of the least-rated rosters in FBS —
a larger error than the zeros are. This is known and accepted rather than open (see
`DECISIONS.md`); the column is deliberately left untouched, because nulling the zeros to "fix"
them would extend the same imputation error across all 125 academy games since 2022.

---

## Rankings (`cfb_silver.rankings`)

| column | meaning |
|---|---|
| `poll` | Which poll — AP Top 25, Coaches Poll, CFP rankings |
| `rank` | Position in that poll, 1 = best |
| `points` | Voting points received |
| `first_place_votes` | Count of first-place votes |

Grain is season, week, poll, and team, so filter to one `poll` before aggregating or you will
count teams two or three times. Currently ingested but not surfaced in gold; the playoff
simulator uses `preseason_rank` from its own composite as a ranking stand-in rather than a poll.

---

## Form and record (`cfb_gold.team_week`)

One row per team per week, holding that team's record **cumulative through that week**.

| column | meaning |
|---|---|
| `games_played`, `wins`, `losses` | Season totals through this week |
| `win_pct` | `wins / games_played` |
| `point_diff` | Cumulative points scored minus allowed |
| `avg_margin_l3` | Mean margin over the last three games |
| `fbs_games_played`, `fbs_wins` | Same counts, non-FBS opponents excluded |
| `win_pct_fbs` | `fbs_wins / fbs_games_played` |
| `avg_margin_l3_fbs` | Mean margin over the last three **FBS** games — not the FBS games among the last three |
| `points_for`, `points_against`, `won`, `opponent`, `is_home` | That week's individual game |
| `conference` | Conference **as of that season**, before any later realignment |
| `conference_group` | `Power4`, `G6`, `Independent`, or `Other` |

Two traps worth internalizing.

**A week-W row includes week W's game.** The cumulative columns are computed through the current
row, so if you join this table to a game on `week <= game_week` you hand yourself the result of
the game you are trying to predict. `gold_game_features` joins on `week <` for exactly this
reason, and a test enforces it.

**`conference` is historical, not current.** A 2016 Oregon row reads Pac-12, not Big Ten. That is
correct and intentional; do not "fix" it when reporting on past seasons.

---

## Market and betting columns

All of these describe the sportsbook's opinion. None are model inputs — `FEATURE_COLS` excludes
them deliberately, so that model-versus-market comparisons stay meaningful.

| column | meaning |
|---|---|
| `market_spread` | Closing spread, **from the home team's perspective** |
| `market_spread_open` | The spread when the game first opened for betting |
| `market_ou` | Predicted combined score (the total, or over/under) |
| `market_ou_open` | Opening predicted combined score |
| `market_home_ml`, `market_away_ml` | Moneyline prices in American odds |
| `market_home_win_prob_implied` | Home moneyline converted to a probability, **vig included** |
| `market_home_win_prob_novig` | The same, with the bookmaker's margin removed |
| `line_provider` | Provider of the current spread and total |
| `opening_line_provider` | Provider of both opening prices |
| `moneyline_provider` | Provider of both moneyline prices |

The three provider columns are intentionally separate. A Consensus row commonly has a current
spread but no moneyline or opening price; forcing one provider across every field created avoidable
nulls. Each pair now comes from one internally coherent quote, and each silver market table
contains only complete rows for its own contract. A missing gold value means no provider published
that market, not that a sparse provider happened to win the row-selection rule.

### The spread's sign

**Negative means the home team is favored.** `-7.0` means the home team is expected to win by
seven. The data confirms it: `market_spread` correlates -0.661 with the actual home margin, the
average spread is -4.1 against an average home margin of +4.03, and 61% of games open with a
negative spread, which is home-field advantage showing up in the prices. Favorites win 73.7% of
the time.

### Why there are two implied probabilities

A book prices both sides so that the implied probabilities sum to more than one. In this data they
average **1.044**, and that 4.4% overround is the house's cut rather than an opinion about the
game. Left in, it inflates the home side by 2.5 percentage points of probability on average — the
raw home number averages 0.588 against a de-vigged 0.563.

- `market_home_win_prob_implied` is the raw conversion — what the posted price literally says.
- `market_home_win_prob_novig` divides by the sum of both sides, so home and away total exactly 1.

Use the de-vigged one for anything comparative, which is what `model_minus_market_home` does. It
also means `1 - market_home_win_prob_novig` is a valid away probability, which was never true of
the raw column.

Moneylines are the sparsest current market here: 3,771 of 8,326 FBS-vs-FBS games have a complete
two-way price, or 45%. They are entirely absent from 2015-2020, then cover 91-98% of each season
from 2021 onward. Any model-versus-market analysis is therefore a recent-seasons analysis.

---

## Model outputs

| column | where | meaning |
|---|---|---|
| `model_home_win_prob` | `game_predictions`, `matchup_card` | Probability the home team wins, from the logistic model. Null until scoring has run |
| `model_version` | same | Which registered model version produced it |
| `scored_at` | same | When scoring ran |
| `model_minus_market_home` | `matchup_card` | `model_home_win_prob` − `market_home_win_prob_novig`. Positive means the model is higher on the home team than the market is |

`model_minus_market_home` is a **disagreement, not an edge**. A gap means the model and the market
see the game differently, and on holdout data the market is the more accurate of the two.

### `preseason_team_ratings`

| column | meaning |
|---|---|
| `rating` | Weighted composite of standardized inputs, used to seed playoff simulations |
| `preseason_rank` | Rank by `rating`, 1 = best |

`rating` is a z-score blend, with defensive terms inverted so that higher is always better:
45% `sp_overall`, 20% `sp_offense`, 15% `sp_defense` (inverted), 10% `ppa_offense`,
5% `ppa_defense` (inverted), and 5% `talent`. Because the inputs are standardized, `rating` is in
standard deviations, not points — unlike SP+.

### `weekly_brief`

One row per `game_id + team`: every game produces a home-team perspective and an away-team
perspective. The away row flips the home probability, spread, and model-market difference, so all
values read naturally from `team`'s point of view. `season_type` is part of every row because
regular and postseason schedules both use week numbers starting at 1.

`WEEK = None` refreshes all weeks in the requested season/type. Writes replace only that scope and
preserve every other historical season/type already stored.

---

## Identity and outcome columns

| column | meaning |
|---|---|
| `game_id` | CFBD's game identifier, unique per game |
| `season` | The year the season kicked off in. A January bowl belongs to the previous season |
| `week` | Week number within the season |
| `season_type` | `regular` or `postseason` |
| `completed` | Whether the game has been played |
| `neutral_site` | Neither team is at home — bowls and kickoff games |
| `conference_game` | Both teams in the same conference |
| `margin_home` | `home_points` − `away_points`. Positive means the home team won |
| `total_points` | Combined score, comparable against `market_ou` |
| `home_won` | Null until the game is completed |
| `is_fbs_game` | At least one FBS participant (`silver_games`) |
| `home_feature_week` / `away_feature_week` | Week label on the `team_week` row supplying form. Do not compare these across regular/postseason |
| `home_feature_start_date` / `away_feature_start_date` | Actual as-of cutoff for form — always strictly before the predicted game's `start_date` |
| `is_fbs` | FBS that season (`silver_team_seasons`) or currently (`silver_teams`) |
| `is_notre_dame` | Flags the one team with a playoff rule of its own; see `docs/CFP_RULES.md` |
| `_source_path`, `_ingest_mode` | Lineage: which landed file a row came from, and whether via backfill or incremental refresh |

In `game_features` and `matchup_card` every team-level stat appears twice, prefixed `home_` and
`away_`, plus a handful of pre-computed differences (`sp_overall_diff`, `ppa_offense_diff`,
`ppa_defense_diff`, `talent_diff`, and their `_prior` variants). A `*_diff` is always home minus
away, so positive favors the home team — except for the defensive ones, where lower is better and
a negative difference is the home team's advantage.

---

## Coverage gaps, in one place

| what | gap |
|---|---|
| `sp_sos` | 2015-2018 only; null from 2019 |
| `sp_special_teams` | Missing for 2020 and 2021 |
| `sp_overall` | Two teams missing in 2017 |
| `talent` | Air Force and Navy null in 2025 — a real gap, and median imputation mistakes it for average talent. The `0`s from 2022 are genuine values, not gaps |
| Moneylines | 3,771 of 8,326 FBS-vs-FBS games (45%); none in 2015-2020, 91-98% per season from 2021 |
| `_prior` ratings | All 765 games of 2015 (no 2014 backfill), plus 82-115 games a season for teams promoted from FCS |
| Form columns | Null for the 902 week-1 games, since no prior week exists, and for another ~100 where a team had not yet played an FBS opponent. The training pipeline imputes them |
| 2020 season | 127 teams and far fewer games — COVID. Expect it to look strange in any season-over-season trend |
