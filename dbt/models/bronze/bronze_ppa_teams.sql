{{ config(alias='ppa_teams') }}

{%- set projection -%}
    cast(season as int) as season,
    team,
    conference,
    cast(offense.overall as double) as ppa_offense,
    cast(offense.passing as double) as ppa_offense_passing,
    cast(offense.rushing as double) as ppa_offense_rushing,
    cast(defense.overall as double) as ppa_defense,
    cast(defense.passing as double) as ppa_defense_passing,
    cast(defense.rushing as double) as ppa_defense_rushing
{%- endset -%}

{{ cfbd_union('ppa_teams', projection) }}
