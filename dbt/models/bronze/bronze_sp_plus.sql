{{ config(alias='sp_plus') }}

{%- set projection -%}
    cast(year as int) as season,
    team,
    conference,
    cast(rating as double) as sp_overall,
    cast(ranking as int) as sp_rank,
    cast(secondOrderWins as double) as sp_second_order_wins,
    cast(sos as double) as sp_sos,
    cast(offense.rating as double) as sp_offense,
    cast(defense.rating as double) as sp_defense,
    cast(specialTeams.rating as double) as sp_special_teams
{%- endset -%}

{{ cfbd_union('sp_plus', projection) }}
