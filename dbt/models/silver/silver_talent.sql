{{ config(alias='talent') }}

with typed as (

    select
        season,
        team,
        talent
    from {{ ref('bronze_talent') }}
    where team is not null
      and season is not null

)

select *
from typed
qualify row_number() over (partition by season, team order by talent desc nulls last) = 1
