-- Form must be drawn from a game strictly before the predicted game's start. A team_week row is
-- cumulative through its source game, so an inclusive cutoff leaks the outcome being predicted.
-- Timestamps, rather than week numbers, also preserve chronology when postseason Week 1 follows
-- regular Week 15.
select
    game_id,
    season,
    season_type,
    week,
    start_date,
    home_feature_start_date,
    away_feature_start_date
from {{ ref('gold_game_features') }}
where home_feature_start_date >= start_date
   or away_feature_start_date >= start_date
