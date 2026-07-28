select
    game_id,
    provider,
    count(*) as n
from {{ ref('silver_lines_all') }}
group by game_id, provider
having count(*) > 1
