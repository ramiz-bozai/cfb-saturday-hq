{{ config(alias='lines_all') }}

-- One row per game per sportsbook. silver_lines picks a single preferred provider.
with exploded as (

    select
        b.game_id,
        b.season,
        b.week,
        b.season_type,
        b.home_team,
        b.away_team,
        line.provider as provider,
        cast(line.spread as double) as spread,
        line.formattedSpread as formatted_spread,
        cast(line.spreadOpen as double) as spread_open,
        cast(line.overUnder as double) as over_under,
        cast(line.overUnderOpen as double) as over_under_open,
        cast(line.homeMoneyline as double) as home_moneyline,
        cast(line.awayMoneyline as double) as away_moneyline,
        b._source_path,
        b._ingest_mode
    from {{ ref('bronze_lines') }} as b
    lateral view outer explode(b.lines) exploded_lines as line

)

-- Lines move, so the same game+provider lands in several drops. Keep the newest quote.
select *
from exploded
qualify row_number() over (
    partition by game_id, provider
    order by {{ latest_ingest_first() }}
) = 1
