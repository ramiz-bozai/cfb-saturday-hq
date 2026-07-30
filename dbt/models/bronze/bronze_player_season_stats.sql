{{ config(alias='player_season_stats') }}

{%- set projection -%}
    cast(season as int) as season,
    cast(playerId as string) as athlete_id,
    player as player_name,
    position,
    team,
    conference,
    category,
    statType as stat_type,
    cast(stat as double) as stat_value
{%- endset -%}

{{ cfbd_union('player_season_stats', projection) }}
