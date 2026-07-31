{{ config(alias='nfl_udfa') }}

{%- set projection -%}
    cast(rookie_year as int) as rookie_year,
    cast(gsis_id as string) as gsis_id,
    first_name,
    last_name,
    display_name,
    football_name,
    college,
    college_name,
    nfl_team,
    position,
    cast(draft_number as int) as draft_number,
    cast(rookie_season as int) as rookie_season
{%- endset -%}

{{ manual_union('nfl_udfa', projection) }}
