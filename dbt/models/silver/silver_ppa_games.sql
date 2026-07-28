{{ config(alias='ppa_games') }}

with typed as (

    select
        game_id,
        season,
        week,
        team,
        conference as conference_raw,
        {{ normalize_conference('conference') }} as conference,
        opponent,
        ppa_offense,
        ppa_defense,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_ppa_games') }}
    where game_id is not null
      and team is not null

)

select *
from typed
qualify row_number() over (
    partition by game_id, team
    order by {{ latest_ingest_first() }}
) = 1
