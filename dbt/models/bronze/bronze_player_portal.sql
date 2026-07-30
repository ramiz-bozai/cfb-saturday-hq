{{ config(alias='player_portal') }}

{%- set projection -%}
    cast(season as int) as season,
    firstName as first_name,
    lastName as last_name,
    position,
    origin,
    destination,
    cast(transferDate as timestamp) as transfer_date,
    cast(rating as double) as transfer_rating,
    cast(stars as int) as transfer_stars,
    eligibility
{%- endset -%}

{{ cfbd_union('player_portal', projection) }}
