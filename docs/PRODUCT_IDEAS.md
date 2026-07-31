# Saturday HQ product ideas

This is a parking lot for turning Saturday HQ from an analytics workbench into a useful fan
product. Nothing here is committed scope.

## Honest current assessment

The underlying engineering project is strong. It demonstrates ingestion, dbt, Delta Lake, Unity
Catalog, MLflow, scheduled workflows, SQL analytics, simulation, and a Databricks App.

The current fan experience is much weaker. It exposes tables and statistics without consistently
answering the questions a fan has:

- Who is likely to win?
- Why?
- Which games should I watch?
- Is an upset plausible?
- What does this game mean for the playoff?
- Is my team improving?
- How trustworthy is the model?

The Matchup tab is effectively a transposed database row. The Slate is another dataframe. The
weekly brief converts values into prose but still expects the fan to understand SP+, PPA, talent,
market probability, and model probability.

## Product north star

> Saturday HQ tells me which games matter, who is likely to win, why, and what each result means
> for the playoff.

ESPN already answers what happened, when a game starts, and who is on the roster. Saturday HQ
should focus on interpretation, explanation, uncertainty, and consequences.

## What the project predicts today

### Matchup win probability

The logistic-regression model predicts the probability that the home team wins. It does not
predict an exact score or margin.

Inputs include:

- Prior-season SP+ and offensive/defensive PPA
- Current roster talent
- Current-season win percentage against FBS opponents
- Average margin over the last three FBS games
- Neutral-site context

Sportsbook lines are excluded from training. The model is an independent football opinion; the
market is used only as a comparison.

Current 2025 holdout results after correcting feature chronology:

- Accuracy: 68.3%
- AUC: 0.7565
- Brier score: 0.2019

The de-vigged market performed better:

- Accuracy: 72.4%
- AUC: 0.7954
- Brier score: 0.1810

The model therefore has real predictive signal, but it should not be presented as beating the
market or providing betting picks.

### Model versus market

`model_minus_market_home` measures disagreement.

Example:

- Saturday HQ gives Georgia 64%.
- The de-vigged market gives Georgia 58%.
- Saturday HQ is six percentage points more optimistic.

That is a reason to investigate the matchup, not proof of a betting edge.

### Season and playoff simulation

The simulator repeatedly resolves the remaining regular-season schedule, ranks teams using wins
and preseason rating, applies the implemented 2026 CFP automatic-qualifier rules, and records each
team's result.

It produces:

- Mean and median wins
- Win-total floor and ceiling
- Playoff probability
- Average seed when selected

The simulator is a committee stand-in, not an official CFP model.

## Why the App still has room to grow

Season Preview (roster continuity) is now a real fan surface. Remaining gaps for in-season tabs:

- Matchup still presents columns more than conclusions.
- It does not explain why the model produced a probability.
- It does not show how a result changes playoff odds.
- It has no persistent pregame prediction record.
- It defaults to the date-derived completed season until August, even though fans may already care
  about the upcoming schedule.
- A completed season has no remaining uncertainty, making its projections deterministic.

## Phase 1: make existing data understandable

This phase should require little or no new modeling.

### Weekly game cards

**Status: implemented.** The Slate now presents responsive cards prioritized by close-game and
model-market-disagreement signals, with separate My Teams and Games to Watch sections. Each card
shows records, kickoff or final status, the model pick, de-vigged market context, spread, fan-facing
labels, and available matchup indicators. Logos, locations, and true per-prediction feature
contributions remain future data/modeling work.

Replace the raw Slate dataframe with cards that show:

- Team names, logos, and records
- Kickoff time and location
- Predicted winner and win probability
- De-vigged market probability
- Spread
- Upset potential
- Model-market disagreement
- Two or three plain-English matchup reasons

Example:

> **Oregon 61% over Michigan**
>
> Oregon has the stronger offense and better recent FBS form. Michigan has the defensive
> advantage. The market is slightly more confident in Oregon than Saturday HQ.

### Fan-oriented weekly sections

- Games of the week
- My Teams
- Toss-ups
- Upset Watch
- Largest model-market disagreements
- High-confidence favorites
- Games with the largest playoff implications

Use “disagreement,” not “edge,” when comparing against the market.

### Team page

Give each team one useful home:

- Record and FBS-only record
- SP+ ranking
- Offensive and defensive strengths
- Season trajectory
- Upcoming schedule with win probabilities
- Expected win total
- Playoff odds
- Best win and worst loss
- Most important remaining game

Prefer charts and labeled comparisons over raw rows.

### Better defaults

Default to the season fans care about:

- Active season when games are underway
- Newest season with scheduled games during the offseason
- Most recent completed season only when no upcoming schedule exists

## Phase 2: explain and establish trust

### Per-game prediction explanations

Logistic regression can expose each standardized feature's contribution to a prediction. Store
and display the highest-impact positive and negative factors.

Possible output:

> **Why Georgia is favored**
>
> - Prior SP+ advantage: +9 percentage points
> - Roster talent advantage: +6
> - Recent FBS form: +3
> - Opponent defensive matchup: -2

Create a prediction-explanations table with:

- `game_id`
- Base probability
- Feature name
- Human-readable feature label
- Feature contribution
- Contribution rank
- Final probability
- Model version

Do not substitute generic prose for actual model contributions.

### Pregame prediction history

Add an append-only prediction table that captures what was known before kickoff:

- `game_id`
- Prediction timestamp
- Model version
- Model probability
- Market probability and provider
- Feature cutoff timestamp
- Actual result after completion

The current overwrite table is useful for serving the latest prediction but cannot prove what the
model said before a game. Keep a latest view over the append-only history.

### Model accountability page

Show:

- Weekly and season record
- Brier score and log loss
- Calibration by probability bucket
- Performance by confidence range
- Model versus market over time
- Every historical pregame prediction

Fan-friendly calibration example:

> Teams given a 70–79% chance won 74% of the time.

### Walk-forward evaluation

Create honest out-of-sample predictions for every historical evaluation season:

1. Train through 2018 and predict 2019.
2. Train through 2019 and predict 2020.
3. Continue through 2025.
4. Combine the untouched predictions into one backtest.
5. After evaluation, fit the production model on every completed season.

Historical predictions from seasons used during training must not be presented as backtest
evidence.

## Phase 3: build the differentiator

### Conditional playoff scenarios

For an important upcoming game, run the simulator twice:

- Force Team A to win.
- Force Team A to lose.

Then show:

> **Penn State playoff odds**
>
> - Current: 42%
> - With a win: 68%
> - With a loss: 17%

Extend this to:

- Conference championship odds
- Most important remaining game
- Elimination scenarios
- Teams helped or hurt by another matchup
- “What needs to happen?” playoff paths

This is the strongest opportunity to offer something meaningfully different from a normal team or
matchup page.

### Personalized fan feed

- Favorite teams
- Upcoming games
- Upset and playoff-stakes alerts
- Weekly probability changes
- “What changed since Monday?” explanations

## Modeling ideas for later

- True as-of weekly SP+/PPA snapshots once enough snapshot history exists
- Separate expected-margin or score model
- Injury, quarterback, transfer, and coaching context
- Weather and travel features
- Better FCS handling rather than excluding unrated opponents
- Actual conference championship logic instead of a conference-wins proxy
- Probability calibration layer if future backtests show systematic overconfidence

Do not add an exact-score prediction merely because fans recognize scores. It should wait until
there is a model that can be honestly evaluated for that target.

## Things not to prioritize

- More raw statistics on the Matchup tab
- More tabs without a fan question behind them
- Betting recommendations
- An LLM chatbot before the core weekly experience is useful
- Claims that the model beats the market
- Cosmetic polish before predictions are explained and historically accountable

## Suggested success measures

- A fan can identify the five most interesting games in under one minute.
- Every displayed prediction has a short, evidence-backed explanation.
- Every completed game retains its original pregame prediction.
- The App can answer how a win or loss changes playoff odds.
- Model performance is visible and calibrated, not asserted.
- A team page explains current quality, trajectory, schedule, and stakes without requiring the data
  dictionary.

## Season Preview

**Status: landed (analytics backbone + React fan UI).** Season Preview gold models are built in
prod for 2026 (constructed rosters from 2025 + production weighting + NFL draft exits).
The Databricks App is a **React + Express** SPA (Streamlit retired) with a polished
Season Preview (overview + team) and functional ports of Home / Slate / Matchup /
Projections / Brief.

CFBD may still lack a published 2026 roster until near camp — Season Preview then constructs
rosters from prior season − portal − draft + arrivals. Re-run
`notebooks/06_preview_ingest.py` or `scripts/sync_preview_domains.py` when portal/roster
data updates, then `dbt build --select bronze_player_portal+` (and related bronze+).

Current pipelines stop at team-season and team-week grains for in-season tabs. Player-level
CFBD domains power Season Preview.

### CFBD domains to add

| Domain | Endpoint | Role |
| --- | --- | --- |
| `rosters` | `/roster` | Current/prior roster, positions, class, eligibility |
| `player_portal` | `/player/portal` | Transfer arrivals and departures |
| `player_returning` | `/player/returning` | Team returning-production percentages |
| `player_usage` | `/player/usage` | Prior-season usage / snap share |
| `player_season_stats` | `/stats/player/season` | Box-score production by category |
| `player_season_overview` | `/player/season` or `/ppa/players/season` | PPA / success / explosiveness |
| `recruiting_players` | `/recruiting/players` | Stars, rating, position, class year |

Treat portal + recruiting players as season-static (refresh periodically in the offseason).
Treat returning production as a season-static snapshot once CFBD publishes it for the upcoming
year. Player stats/usage/overview are historical backfills through the prior completed season.

### Design principles

- Weight transfers by **prior usage and production**, not recruiting stars alone.
- Separate **impact** vs **depth** for both additions and losses.
- Prefer **unit continuity grades** over a single returning-starters count.
- Keep QB rooms as their own surface; quarterback uncertainty dominates offseason narrative.
- Never claim projected starters without an explicit rule (usage threshold + roster presence).

### Gold tables to build

1. `player_season` — one row per athlete-season: team, position group, usage, production
   metrics, PPA, recruiting profile.
2. `roster_snapshot` — athlete on a team for a given season, linked to prior-season production.
3. `portal_moves` — from/to, date, prior usage, prior production, impact vs depth class.
4. `returning_production_team` — offense/defense and category-level returning %.
5. `unit_continuity` — grade inputs per team × position group × season.
6. `transfer_dependency` — team-level dependency score and components.
7. `qb_room` — classified QB room for each team-season.
8. Serving views / `matchup`-style cards for the Season Preview tab (overview + team detail).

### Unit continuity grades

Position groups: QB, RB, WR/TE, OL, DL, LB, Secondary, Special teams.

For each group show:

- Production returning
- Usage returning
- Recruiting talent retained / added
- Transfer additions and departures (impact vs depth)
- Experience
- Replacement risk
- Net production / talent gained

### Portal impact ledger

For each team:

- Impact additions / depth additions
- Impact losses / depth losses
- Net production gained
- Net talent gained
- Projected starters added / lost

Impact rule (v1): prior-season usage above a position-specific threshold **or** top-N share of
team production at that position. Stars alone never create “impact.”

### Transfer dependency score

Team-level composite from:

- Share of expected starting usage from transfers
- Share of departed production replaced by transfers
- Count of critical units relying on new arrivals
- Average prior production of incoming transfers

### Replacement risk

Highlight departed production that returning/incoming players do not cover.

Example shape:

> Highest replacement risk: Edge
> 71% of team sack production left; no returning player had more than two sacks.

### QB room page

**Landed (Phase A):** returning-starter status, career attempts / weighted career PPA, prior
attempts, rushing contribution + rush-share proxy, INT rate + turnover rate (INT+fumbles when
present), recruiting stars/rating, transfer count / last origin, backup flag + second-QB prior
attempts, room classification rule tree.

**Deferred (Phase B — need endpoints not landed today):** success rate, explosiveness, sack rate,
team W-L with each QB. Do not surface these in the UI until they exist in gold.

Room classes:

- Proven elite starter
- Proven average starter
- High-upside transfer
- Unproven competition
- Experienced but limited
- Major uncertainty

### App surfaces

The fan App lives under `app/` (Vite React client + Express API over Databricks SQL).

**Season Preview — overview (all FBS, conference filter):**

- Thinnest returning production
- Most transfer-dependent
- Portal winners / losers
- Hottest replacement-risk callouts
- QB rooms by uncertainty class

**Season Preview — team:**

- Hero (room class + published/constructed badge)
- Returning production dashboard (offense/defense + categories)
- Transfer dependency + portal impact ledger
- Unit continuity grade grid (worst first)
- Replacement-risk alerts
- Portal arrivals / departures (impact first)
- QB room cards (Phase A fields only)

**Also shipped (functional, on-theme):** Home demo profile, weekly Slate cards, Matchup,
Projections, Brief.

### Build order (offseason track)

1. **Ingest foundations** — *(done)* CFBD client + domain tiers + historical/offseason pull;
   bronze + silver with athlete IDs and position-group mapping; draft picks.
2. **Returning production + unit continuity** — *(done)* gold + Season Preview overview/team UI.
3. **Portal impact ledger** — *(done)* usage-weighted adds/losses and net production/talent.
4. **Transfer dependency + replacement risk** — *(done)* team scores and callouts (portal + draft).
5. **QB room** — *(done Phase A)* classification and team page section.
6. **Polish** — *(partial)* conference filters and in-app team deep links landed; shareable
   external deep links still optional.

Do not ship an empty Season Preview tab backed by stubs. Ship after silver player data exists for at
least the prior season and the upcoming roster/portal snapshot.

## Recommended order

1. Weekly game cards and fan-oriented rankings *(done for cards)*
2. **Season Preview track** *(analytics + React Season Preview UI landed)*
3. Fix Week 1 preseason feature join (prior SP+/talent available before any games)
4. Team page and better season defaults
5. Per-game model contributions
6. Append-only prediction history and accountability
7. Walk-forward backtest and production refit
8. Conditional playoff scenarios
9. Personalized alerts and deeper modeling inputs
