{{ config(alias='conferences') }}

{%- set projection -%}
    cast(id as int) as conference_id,
    name as conference_name,
    abbreviation
{%- endset -%}

{{ cfbd_union('conferences', projection) }}
