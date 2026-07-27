select
    season,
    team,
    week,
    count(*) as n
from {{ ref('gold_team_week') }}
group by season, team, week
having count(*) > 1
