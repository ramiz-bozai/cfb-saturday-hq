{{ config(alias='teams_fbs') }}

{%- set projection -%}
    cast(id as int) as team_id,
    school as team,
    mascot,
    abbreviation,
    conference,
    classification,
    color,
    alternateColor as alternate_color,
    logos
{%- endset -%}

{{ cfbd_union('teams_fbs', projection) }}
