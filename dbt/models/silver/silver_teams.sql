{{ config(alias='teams') }}

with typed as (

    select
        team_id,
        team,
        mascot,
        abbreviation,
        {{ normalize_conference('conference') }} as conference,
        classification,
        color,
        alternate_color,
        logos,
        true as is_fbs,
        lower(team) = 'notre dame' as is_notre_dame,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_teams_fbs') }}
    where team is not null

)

select *
from typed
qualify row_number() over (
    partition by team
    order by {{ latest_ingest_first() }}
) = 1
