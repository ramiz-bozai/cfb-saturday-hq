{{ config(alias='player_usage') }}

{%- set projection -%}
    cast(season as int) as season,
    cast(id as string) as athlete_id,
    name as player_name,
    position,
    team,
    conference,
    cast(usage.overall as double) as usage_overall,
    cast(usage.pass as double) as usage_pass,
    cast(usage.rush as double) as usage_rush,
    cast(usage.firstDown as double) as usage_first_down,
    cast(usage.secondDown as double) as usage_second_down,
    cast(usage.thirdDown as double) as usage_third_down,
    cast(usage.standardDowns as double) as usage_standard_downs,
    cast(usage.passingDowns as double) as usage_passing_downs
{%- endset -%}

{{ cfbd_union('player_usage', projection) }}
