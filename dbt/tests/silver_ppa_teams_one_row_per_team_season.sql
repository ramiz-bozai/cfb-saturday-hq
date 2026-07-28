select
    season,
    team,
    count(*) as n
from {{ ref('silver_ppa_teams') }}
group by season, team
having count(*) > 1
