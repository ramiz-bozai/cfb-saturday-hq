{{ config(alias='recruiting_players') }}

with typed as (

    select
        recruit_id,
        athlete_id,
        recruit_type,
        class_year,
        recruiting_rank,
        player_name,
        high_school,
        committed_to,
        position,
        {{ position_group('position') }} as position_group,
        height,
        weight,
        cast(stars as int) as stars,
        rating,
        city,
        state_province,
        country,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_recruiting_players') }}
    where class_year is not null
      and nullif(trim(player_name), '') is not null

)

select *
from typed
qualify row_number() over (
    partition by class_year, coalesce(athlete_id, recruit_id), coalesce(committed_to, '')
    order by {{ latest_ingest_first() }}
) = 1
