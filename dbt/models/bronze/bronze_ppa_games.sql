{{ config(alias='ppa_games') }}

{%- set projection -%}
    cast(gameId as bigint) as game_id,
    cast(season as int) as season,
    cast(week as int) as week,
    team,
    conference,
    opponent,
    cast(offense.overall as double) as ppa_offense,
    cast(defense.overall as double) as ppa_defense
{%- endset -%}

{{ cfbd_union('ppa_games', projection) }}
