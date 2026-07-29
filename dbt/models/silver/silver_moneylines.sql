{{ config(alias='moneylines') }}

/*
    One complete two-way moneyline from one sportsbook per game.

    Both sides must come from the same provider: de-vigging prices assembled from different books
    would not represent any real market. Older seasons with no moneylines correctly have no row.
*/
with prioritized as (

    select
        *,
        {{ market_provider_priority() }} as provider_priority
    from {{ ref('silver_lines_all') }}
    where provider is not null
      and home_moneyline is not null
      and away_moneyline is not null

)

select
    game_id,
    season,
    week,
    season_type,
    home_team,
    away_team,
    provider,
    home_moneyline,
    away_moneyline
from prioritized
qualify row_number() over (
    partition by game_id
    order by provider_priority, provider
) = 1
