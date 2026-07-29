{{ config(alias='teams_fbs') }}

{#- The /teams/fbs payload carries no year, so the season comes from the landing path. -#}
{%- set projection -%}
    {{ landing_season() }} as season,
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
