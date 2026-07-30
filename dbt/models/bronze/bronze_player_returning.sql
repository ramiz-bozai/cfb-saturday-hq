{{ config(alias='player_returning') }}

{%- set projection -%}
    cast(season as int) as season,
    team,
    conference,
    cast(totalPPA as double) as total_ppa,
    cast(totalPassingPPA as double) as total_passing_ppa,
    cast(totalReceivingPPA as double) as total_receiving_ppa,
    cast(totalRushingPPA as double) as total_rushing_ppa,
    cast(percentPPA as double) as percent_ppa,
    cast(percentPassingPPA as double) as percent_passing_ppa,
    cast(percentReceivingPPA as double) as percent_receiving_ppa,
    cast(percentRushingPPA as double) as percent_rushing_ppa,
    cast(usage as double) as usage,
    cast(passingUsage as double) as passing_usage,
    cast(receivingUsage as double) as receiving_usage,
    cast(rushingUsage as double) as rushing_usage
{%- endset -%}

{{ cfbd_union('player_returning', projection) }}
