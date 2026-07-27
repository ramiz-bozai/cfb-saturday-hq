-- Metric definitions for Dashboards / Genie (reference)
-- Point Genie at gold tables only.

-- SP+: Team SP+ overall / offense / defense from CFBD /ratings/sp (season level).
-- PPA: Predicted Points Added from CFBD /ppa/teams (season) and /ppa/games (game).
-- FBS only: gold marts are filtered to FBS vs FBS where modeling requires it.
-- Market implied probability: converted from American moneyline when present.
-- Model win probability: logistic model on SP+/PPA/talent/form features; lines excluded from training.
-- Playoff odds: Monte Carlo using model probs + published 2026 CFP AQ rules; not official.

-- Example certified queries
-- SELECT season, team, sp_overall, ppa_offense, ppa_defense
-- FROM cfb_saturday_hq.cfb_gold.team_week
-- WHERE season = 2025 AND week = 10
-- ORDER BY sp_overall DESC;

-- SELECT season, week, home_team, away_team, model_home_win_prob,
--        market_home_win_prob_implied, model_minus_market_home, market_spread
-- FROM cfb_saturday_hq.cfb_gold.matchup_card
-- WHERE season = 2026 AND week = 1
-- ORDER BY abs(model_minus_market_home) DESC NULLS LAST;
