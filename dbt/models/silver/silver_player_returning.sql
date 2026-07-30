{{ config(alias='player_returning') }}

with typed as (

    select
        season,
        team,
        {{ normalize_conference('conference') }} as conference,
        total_ppa,
        total_passing_ppa,
        total_receiving_ppa,
        total_rushing_ppa,
        percent_ppa,
        percent_passing_ppa,
        percent_receiving_ppa,
        percent_rushing_ppa,
        usage,
        passing_usage,
        receiving_usage,
        rushing_usage,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_player_returning') }}
    where season is not null
      and team is not null

)

select *
from typed
qualify row_number() over (
    partition by season, team
    order by {{ latest_ingest_first() }}
) = 1
