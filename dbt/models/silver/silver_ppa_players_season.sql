{{ config(alias='ppa_players_season') }}

with typed as (

    select
        season,
        athlete_id,
        player_name,
        position,
        {{ position_group('position') }} as position_group,
        team,
        {{ normalize_conference('conference') }} as conference,
        avg_ppa_all,
        avg_ppa_pass,
        avg_ppa_rush,
        total_ppa_all,
        total_ppa_pass,
        total_ppa_rush,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_ppa_players_season') }}
    where season is not null
      and athlete_id is not null
      and team is not null
      and nullif(trim(player_name), '') is not null

)

select *
from typed
qualify row_number() over (
    partition by season, athlete_id, team
    order by {{ latest_ingest_first() }}
) = 1
