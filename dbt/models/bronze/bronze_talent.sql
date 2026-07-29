{{ config(alias='talent') }}

{#- /talent returns `team`, unlike /teams/fbs which returns `school`. -#}
{%- set projection -%}
    cast(year as int) as season,
    team,
    cast(talent as double) as talent
{%- endset -%}

{{ cfbd_union('talent', projection) }}
