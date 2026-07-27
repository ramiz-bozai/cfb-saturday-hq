{{ config(alias='team_season_stats') }}

{#- Landed for ad-hoc analysis; no silver model depends on it yet. -#}
{%- set projection -%}
    cast(season as int) as season,
    team,
    conference,
    statName as stat_name,
    cast(statValue as double) as stat_value
{%- endset -%}

{{ cfbd_union('team_season_stats', projection) }}
