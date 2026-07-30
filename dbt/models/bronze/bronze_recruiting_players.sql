{{ config(alias='recruiting_players') }}

{%- set projection -%}
    cast(id as string) as recruit_id,
    cast(athleteId as string) as athlete_id,
    recruitType as recruit_type,
    cast(year as int) as class_year,
    cast(ranking as int) as recruiting_rank,
    name as player_name,
    school as high_school,
    committedTo as committed_to,
    position,
    cast(height as double) as height,
    cast(weight as int) as weight,
    cast(stars as int) as stars,
    cast(rating as double) as rating,
    city,
    stateProvince as state_province,
    country
{%- endset -%}

{{ cfbd_union('recruiting_players', projection) }}
