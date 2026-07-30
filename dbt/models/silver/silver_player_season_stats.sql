{{ config(alias='player_season_stats') }}

with typed as (

    select
        season,
        athlete_id,
        player_name,
        position,
        {{ position_group('position') }} as position_group,
        team,
        {{ normalize_conference('conference') }} as conference,
        category,
        stat_type,
        stat_value,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_player_season_stats') }}
    where season is not null
      and athlete_id is not null
      and team is not null
      and category is not null
      and stat_type is not null

)

select *
from typed
qualify row_number() over (
    partition by season, athlete_id, team, category, stat_type
    order by {{ latest_ingest_first() }}
) = 1
