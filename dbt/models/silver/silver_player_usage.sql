{{ config(alias='player_usage') }}

with typed as (

    select
        season,
        athlete_id,
        player_name,
        position,
        {{ position_group('position') }} as position_group,
        team,
        {{ normalize_conference('conference') }} as conference,
        usage_overall,
        usage_pass,
        usage_rush,
        usage_first_down,
        usage_second_down,
        usage_third_down,
        usage_standard_downs,
        usage_passing_downs,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_player_usage') }}
    where season is not null
      and athlete_id is not null
      and team is not null

)

select *
from typed
qualify row_number() over (
    partition by season, athlete_id, team
    order by {{ latest_ingest_first() }}
) = 1
