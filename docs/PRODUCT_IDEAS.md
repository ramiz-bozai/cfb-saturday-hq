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

## Why the App feels underwhelming now

- It presents columns instead of conclusions.
- It does not explain why the model produced a probability.
- It does not rank games by fan interest.
- It does not show how a result changes playoff odds.
- It has no persistent pregame prediction record.
- It defaults to the date-derived 2025 season until August 2026, even though fans may already care
  about the upcoming 2026 schedule.
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

## Recommended order

1. Weekly game cards and fan-oriented rankings
2. Team page and better season defaults
3. Per-game model contributions
4. Append-only prediction history and accountability
5. Walk-forward backtest and production refit
6. Conditional playoff scenarios
7. Personalized alerts and deeper modeling inputs
