{{ config(alias='teams_fbs') }}

{#- Prefer an injected year (preview/historical tag); else derive season from the landing path. -#}
{%- set projection -%}
    coalesce(cast(year as int), {{ landing_season() }}) as season,
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
