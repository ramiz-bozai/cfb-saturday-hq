{{ config(alias='ppa_teams') }}

with typed as (

    select
        season,
        team,
        {{ normalize_conference('conference') }} as conference,
        conference as conference_raw,
        ppa_offense,
        ppa_offense_passing,
        ppa_offense_rushing,
        ppa_defense,
        ppa_defense_passing,
        ppa_defense_rushing
    from {{ ref('bronze_ppa_teams') }}
    where team is not null
      and season is not null

)

select *
from typed
qualify row_number() over (partition by season, team order by ppa_offense desc nulls last) = 1
