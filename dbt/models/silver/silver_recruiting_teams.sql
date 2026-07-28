{{ config(alias='recruiting_teams') }}

with typed as (

    select
        season,
        team,
        recruiting_rank,
        recruiting_points,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_recruiting_teams') }}
    where team is not null
      and season is not null

)

select *
from typed
qualify row_number() over (
    partition by season, team
    order by {{ latest_ingest_first() }}
) = 1
