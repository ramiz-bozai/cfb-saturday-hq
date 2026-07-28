{{ config(alias='conferences') }}

with typed as (

    select
        conference_id,
        conference_name,
        abbreviation,
        {{ normalize_conference('coalesce(abbreviation, conference_name)') }} as conference,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_conferences') }}

)

select *
from typed
qualify row_number() over (
    partition by conference
    order by {{ latest_ingest_first() }}
) = 1
