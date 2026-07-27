{{ config(alias='conferences') }}

with typed as (

    select
        conference_id,
        conference_name,
        abbreviation,
        {{ normalize_conference('coalesce(abbreviation, conference_name)') }} as conference
    from {{ ref('bronze_conferences') }}

)

select *
from typed
qualify row_number() over (partition by conference order by conference_id) = 1
