{{ config(alias='recruiting_teams') }}

{%- set projection -%}
    cast(year as int) as season,
    team,
    cast(rank as int) as recruiting_rank,
    cast(points as double) as recruiting_points
{%- endset -%}

{{ cfbd_union('recruiting_teams', projection) }}
