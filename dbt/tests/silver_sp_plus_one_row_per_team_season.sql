select
    season,
    team,
    count(*) as n
from {{ ref('silver_sp_plus') }}
group by season, team
having count(*) > 1
