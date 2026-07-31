{{ config(alias='player_portal') }}

/*
    Clean portal entries for Preview analytics.

    Drop:
      - eligibility = Withdrawn (entered portal then returned / withdrew)
      - destination IS NULL (no committed school yet — not a completed move)

    Bronze stays a faithful CFBD land; these business filters live here so every
    gold consumer (moves, continuity, ledger, roster construction) sees one grain.
*/

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
        cast(transfer_stars as int) as transfer_stars,
        eligibility,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_player_portal') }}
    where season is not null
      and first_name is not null
      and last_name is not null
      and destination is not null
      and lower(coalesce(eligibility, '')) <> 'withdrawn'

)

select *
from typed
qualify row_number() over (
    partition by season, player_name_key, coalesce(origin, ''), coalesce(destination, ''), transfer_date
    order by {{ latest_ingest_first() }}
) = 1
