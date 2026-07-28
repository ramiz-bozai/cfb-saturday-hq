{{ config(alias='sp_plus') }}

with typed as (

    select
        season,
        team,
        {{ normalize_conference('conference') }} as conference,
        sp_overall,
        sp_rank,
        sp_second_order_wins,
        sp_sos,
        sp_offense,
        sp_defense,
        sp_special_teams,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_sp_plus') }}
    where team is not null
      and season is not null

)

select *
from typed
qualify row_number() over (
    partition by season, team
    order by {{ latest_ingest_first() }}
) = 1
