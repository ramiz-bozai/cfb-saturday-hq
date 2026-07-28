{{ config(alias='lines') }}

-- One market line per game: prefer an explicit consensus, then the major books.
with prioritized as (

    select
        *,
        case
            when lower(provider) = 'consensus' then 0
            when lower(provider) in ('draftkings', 'bovada', 'bolton') then 1
            else 2
        end as provider_priority
    from {{ ref('silver_lines_all') }}
    where provider is not null

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
    spread_open,
    over_under,
    over_under_open,
    home_moneyline,
    away_moneyline
from prioritized
qualify row_number() over (
    partition by game_id
    order by provider_priority, provider
) = 1
