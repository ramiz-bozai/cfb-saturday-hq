{{ config(alias='lines') }}

{#- lines stays nested here; silver_lines_all explodes it one row per provider. -#}
{%- set projection -%}
    cast(id as bigint) as game_id,
    cast(season as int) as season,
    cast(week as int) as week,
    seasonType as season_type,
    homeTeam as home_team,
    awayTeam as away_team,
    lines
{%- endset -%}

{{ cfbd_union('lines', projection) }}
