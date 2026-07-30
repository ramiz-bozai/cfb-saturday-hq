{{ config(alias='player_portal') }}

with typed as (

    select
        season,
        first_name,
        last_name,
        position,
        {{ position_group('position') }} as position_group,
        {{ player_name_key('first_name', 'last_name') }} as player_name_key,
        origin,
        destination,
        transfer_date,
        transfer_rating,
        transfer_stars,
        eligibility,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_player_portal') }}
    where season is not null
      and first_name is not null
      and last_name is not null

)

select *
from typed
qualify row_number() over (
    partition by season, player_name_key, coalesce(origin, ''), coalesce(destination, ''), transfer_date
    order by {{ latest_ingest_first() }}
) = 1
