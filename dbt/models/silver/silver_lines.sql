{{ config(alias='lines') }}

/*
    One complete current spread/total quote per game.

    Opening prices and moneylines have different provider coverage, so they live in their own
    silver models. Requiring this table's fields before ranking prevents a sparse Consensus row
    from winning merely because its provider name is preferred.
*/
with prioritized as (

    select
        *,
        {{ market_provider_priority() }} as provider_priority
    from {{ ref('silver_lines_all') }}
    where provider is not null
      and spread is not null
      and formatted_spread is not null
      and over_under is not null

)

select
    game_id,
    season,
    week,
    season_type,
    home_team,
    away_team,
    provider,
    spread,
    formatted_spread,
    over_under
from prioritized
qualify row_number() over (
    partition by game_id
    order by provider_priority, provider
) = 1
