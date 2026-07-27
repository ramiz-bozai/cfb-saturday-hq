{{ config(alias='talent') }}

{%- set projection -%}
    cast(year as int) as season,
    school as team,
    cast(talent as double) as talent
{%- endset -%}

{{ cfbd_union('talent', projection) }}
