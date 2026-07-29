select
    season,
    team,
    count(*) as n
from {{ ref('silver_team_seasons') }}
group by season, team
having count(*) > 1
