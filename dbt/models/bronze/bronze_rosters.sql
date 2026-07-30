{{ config(alias='rosters') }}

{#- CFBD's `year` field is eligibility class (1=FR…), not season. Season is tagged on ingest
    or taken from the landing path. -#}
{%- set projection -%}
    coalesce(cast(season as int), {{ landing_season() }}) as season,
    cast(id as string) as athlete_id,
    firstName as first_name,
    lastName as last_name,
    team,
    cast(weight as int) as weight,
    cast(height as int) as height,
    cast(jersey as int) as jersey,
    cast(year as int) as class_year,
    position,
    homeCity as home_city,
    homeState as home_state,
    homeCountry as home_country
{%- endset -%}

{{ cfbd_union('rosters', projection) }}
