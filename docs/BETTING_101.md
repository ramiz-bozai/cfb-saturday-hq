# Betting and market data 101

This guide explains the betting terms used in Saturday HQ. The project uses sportsbook data as a
benchmark for what the market thinks; it does not provide betting advice.

## The basic idea

A sportsbook offers prices on possible outcomes. Those prices reflect:

1. The book's estimate of each outcome's probability
2. Market activity and risk
3. The sportsbook's built-in commission—the **vig**

## Spread

The spread is a handicap intended to make both sides competitively priced.

Example:

> Georgia -7.5 vs Florida

This means:

- Georgia is favored.
- For spread grading, subtract 7.5 points from Georgia's score.
- Georgia must win by **8 or more** to cover.
- Florida covers if it wins outright or loses by 7 or fewer.

In this project, `market_spread` is from the **home team's perspective**:

- `-7.5`: home team favored by 7.5
- `+7.5`: home team is a 7.5-point underdog
- `0`: pick'em

The half-point prevents a tie.

### Covering is different from winning

If Georgia wins 24–20:

- Georgia won the game.
- Georgia did not cover -7.5.
- Florida covered +7.5.

The Saturday HQ win-probability model predicts who wins outright. It does not predict who covers.

## Push

A push occurs when the adjusted result lands exactly on the spread.

If Georgia is -7 and wins by exactly 7, the spread bet normally receives its stake back.
Half-point spreads such as -7.5 eliminate pushes.

## Total or over/under

The total is the market's estimate of the teams' combined score.

Example:

> Over/under 52.5

- Over wins if the teams combine for 53 or more.
- Under wins if they combine for 52 or fewer.

A final score of 31–24 totals 55, so the over wins.

Project columns:

- `market_ou`: current or closing total
- `market_ou_open`: opening total
- `total_points`: actual combined score

The current model predicts the winner, not the total.

## Moneyline

The moneyline prices an outright win with no spread.

Example:

- Georgia `-200`
- Florida `+170`

### Negative odds: favorite

`-200` means risking $200 to make $100 profit.

If Georgia wins:

- Stake returned: $200
- Profit: $100
- Total returned: $300

### Positive odds: underdog

`+170` means risking $100 to make $170 profit.

If Florida wins:

- Stake returned: $100
- Profit: $170
- Total returned: $270

Moneyline odds combine probability and payout in one number.

## Implied probability

Moneyline odds can be converted into an implied probability.

For negative American odds:

```text
probability = |odds| / (|odds| + 100)
```

So `-200` becomes:

```text
200 / 300 = 66.7%
```

For positive odds:

```text
probability = 100 / (odds + 100)
```

So `+170` becomes:

```text
100 / 270 = 37.0%
```

But notice:

```text
66.7% + 37.0% = 103.7%
```

Two mutually exclusive outcomes cannot really total 103.7%. The extra 3.7 percentage points
represent the sportsbook's margin.

That is the vig.

## Vig, juice, or overround

These terms describe closely related ideas:

- **Vig/vigorish**: the sportsbook's commission
- **Juice**: common informal name for the vig or the price paid
- **Overround**: how much the raw implied probabilities exceed 100%

If both sides are `-110`:

```text
-110 implies 110 / 210 = 52.38%
```

Both sides together imply:

```text
52.38% + 52.38% = 104.76%
```

The market is not claiming both teams have a 52.38% chance. The additional 4.76 percentage points
are the overround.

This is how a sportsbook can make money over many balanced bets even though one side must win.

## De-vigging

De-vigging removes the bookmaker's margin to estimate the market's underlying probability.

Use the earlier example:

- Georgia raw implied probability: 66.7%
- Florida raw implied probability: 37.0%
- Total: 103.7%

Normalize each side by that total:

```text
Georgia = 66.7 / 103.7 = 64.3%
Florida = 37.0 / 103.7 = 35.7%
```

Now:

```text
64.3% + 35.7% = 100%
```

These are the de-vigged probabilities.

Saturday HQ stores both versions:

- `market_home_win_prob_implied`: raw, vig included
- `market_home_win_prob_novig`: normalized against the away price

For analytical comparisons, use the no-vig version.

## Why de-vigging matters in this project

Suppose:

- Model home probability: 67%
- Raw market home probability: 66%
- De-vigged market home probability: 63%

Using the raw number:

```text
67% - 66% = 1 percentage point
```

Using the market's normalized opinion:

```text
67% - 63% = 4 percentage points
```

The raw number makes the model and market look closer than they are because it still includes the
bookmaker's margin.

Saturday HQ calculates:

```text
model_minus_market_home
= model_home_win_prob - market_home_win_prob_novig
```

A result of `+0.04` means:

> The model assigns the home team a win probability four percentage points higher than the
> de-vigged market does.

It does not automatically mean:

- The market is wrong.
- The model found a profitable bet.
- The difference is statistically meaningful.
- The available price offers positive expected value.

It only measures disagreement.

## Opening versus closing lines

The opening line is the first broadly available price.

The closing line is the last price before the game begins.

Project columns include:

- `spread_open`
- `spread`
- `over_under_open`
- `over_under`

Movement from the opener to the closer can reflect:

- Injuries
- Weather
- Lineup changes
- New information
- Market demand
- The book balancing its exposure
- Sharper market participants correcting an early price

The closing market is usually treated as more informed than the opener.

## Favorites and underdogs

- **Favorite**: expected to win
- **Underdog**: expected to lose
- **Pick'em**: neither side favored
- **Home favorite**: negative home spread
- **Home underdog**: positive home spread

A team can:

- Win and cover
- Win but fail to cover
- Lose but cover
- Lose and fail to cover

For moneylines, only the outright result matters.

## Expected value

Expected value asks whether the payout compensates for the chance of losing.

Suppose your true probability estimate is 60%, and the offered odds are `+100`, which pay even
money.

For a $100 stake:

```text
60% × $100 profit = +$60
40% × $100 loss   = -$40
Expected value    = +$20
```

That would be positive expected value **if** 60% were an accurate probability.

That "if" is the difficult part. A model-market disagreement is not enough; the model must be
better calibrated than the market after accounting for vig and uncertainty.

## Calibration

A calibrated model's probabilities match long-run frequencies:

- Games predicted at 60% should be won about 60% of the time.
- Games predicted at 80% should be won about 80% of the time.

A model can pick many winners but still provide poor probabilities. That is why Saturday HQ tracks
Brier score and log loss, not just accuracy.

## Quick reference

| Term | Meaning |
|---|---|
| Spread | Handicap applied to the score |
| Favorite | Expected winner; negative spread or negative moneyline |
| Underdog | Expected loser; positive spread or usually positive moneyline |
| Cover | Beat the spread |
| Push | Land exactly on the spread or total |
| Total | Predicted combined score |
| Over/under | Bet on combined scoring relative to the total |
| Moneyline | Price on winning outright |
| Implied probability | Probability mathematically embedded in odds |
| Vig/juice | Sportsbook's built-in commission |
| Overround | Raw probabilities exceeding 100% |
| De-vig | Normalize both sides to total 100% |
| Opening line | Initial market price |
| Closing line | Final pregame market price |
| Line movement | Change between opening and current or closing price |
| Model-market difference | Disagreement between model and de-vigged market |
| Expected value | Probability-weighted average profit or loss |
| Calibration | Whether predicted probabilities occur at their stated rates |
