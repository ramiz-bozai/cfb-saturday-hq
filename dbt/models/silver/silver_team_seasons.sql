{{ config(alias='team_seasons') }}

/*
    One row per season per FBS team: membership and conference as they were THAT season.

    silver_teams stays deliberately current-only (one row per team, newest record) and is still
    the right dimension for "who is in FBS now" — the CFP simulator uses it that way. But it
    applies today's roster and today's conferences to every historical season, which for
    2015-2022 mislabels the conference of roughly 22% of teams thanks to realignment, and treats
    eight later FCS-to-FBS movers as though they had always been FBS.

    Anything reading history should join this model on (season, team) instead.
*/

with typed as (

    select
        season,
        team_id,
        team,
        mascot,
        abbreviation,
        {{ normalize_conference('conference') }} as conference,
        classification,
        true as is_fbs,
        lower(team) = 'notre dame' as is_notre_dame,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_teams_fbs') }}
    where team is not null
      and season is not null

)

select *
from typed
qualify row_number() over (
    partition by season, team
    order by {{ latest_ingest_first() }}
) = 1
