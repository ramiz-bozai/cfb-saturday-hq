{{ config(alias='rosters') }}

with typed as (

    select
        season,
        athlete_id,
        first_name,
        last_name,
        team,
        weight,
        height,
        jersey,
        class_year,
        position,
        {{ position_group('position') }} as position_group,
        {{ player_name_key('first_name', 'last_name') }} as player_name_key,
        home_city,
        home_state,
        home_country,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_rosters') }}
    where team is not null
      and season is not null
      and athlete_id is not null
      and nullif(trim(first_name), '') is not null
      and nullif(trim(last_name), '') is not null

)

select *
from typed
qualify row_number() over (
    partition by season, team, athlete_id
    order by {{ latest_ingest_first() }}
) = 1
