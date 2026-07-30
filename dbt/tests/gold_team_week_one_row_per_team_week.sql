select
    season,
    season_type,
    team,
    week,
    count(*) as n
from {{ ref('gold_team_week') }}
group by season, season_type, team, week
having count(*) > 1
