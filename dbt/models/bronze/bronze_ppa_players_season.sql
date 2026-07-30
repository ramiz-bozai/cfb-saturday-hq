{{ config(alias='ppa_players_season') }}

{%- set projection -%}
    cast(season as int) as season,
    cast(id as string) as athlete_id,
    name as player_name,
    position,
    team,
    conference,
    cast(averagePPA.all as double) as avg_ppa_all,
    cast(averagePPA.pass as double) as avg_ppa_pass,
    cast(averagePPA.rush as double) as avg_ppa_rush,
    cast(totalPPA.all as double) as total_ppa_all,
    cast(totalPPA.pass as double) as total_ppa_pass,
    cast(totalPPA.rush as double) as total_ppa_rush
{%- endset -%}

{{ cfbd_union('ppa_players_season', projection) }}
