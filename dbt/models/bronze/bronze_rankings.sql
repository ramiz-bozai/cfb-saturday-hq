{{ config(alias='rankings') }}

{#- polls stays nested here; silver_rankings explodes polls -> ranks. -#}
{%- set projection -%}
    cast(season as int) as season,
    cast(week as int) as week,
    seasonType as season_type,
    polls
{%- endset -%}

{{ cfbd_union('rankings', projection) }}
