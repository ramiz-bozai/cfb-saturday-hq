-- Form must be drawn from a week strictly before the game. A team_week row is cumulative
-- through its own week, so an inclusive cutoff leaks the outcome being predicted into
-- win_pct and avg_margin_l3 — worth ~10 points of holdout accuracy in fake skill.
select
    game_id,
    season,
    week,
    home_feature_week,
    away_feature_week
from {{ ref('gold_game_features') }}
where home_feature_week >= week
   or away_feature_week >= week
