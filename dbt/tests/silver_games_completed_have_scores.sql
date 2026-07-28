-- A completed game must carry both scores; otherwise the labels are unusable.
select
    game_id,
    season,
    week,
    home_points,
    away_points
from {{ ref('silver_games') }}
where completed
  and (home_points is null or away_points is null)
