{{ config(alias='opening_lines') }}

/*
    One complete opening spread/total quote from one sportsbook per game.

    Opening markets were not published in the older CFBD payloads, so those games correctly have
    no row instead of carrying fake zeros or a partially populated quote.
*/
with prioritized as (

    select
        *,
        {{ market_provider_priority() }} as provider_priority
    from {{ ref('silver_lines_all') }}
    where provider is not null
      and spread_open is not null
      and over_under_open is not null

)

select
    game_id,
    season,
    week,
    season_type,
    home_team,
    away_team,
    provider,
    spread_open,
    over_under_open
from prioritized
qualify row_number() over (
    partition by game_id
    order by provider_priority, provider
) = 1
