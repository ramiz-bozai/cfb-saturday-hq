{{ config(alias='games') }}

{%- set projection -%}
    cast(id as bigint) as game_id,
    cast(season as int) as season,
    cast(week as int) as week,
    seasonType as season_type,
    startDate as start_date,
    cast(completed as boolean) as completed,
    cast(neutralSite as boolean) as neutral_site,
    cast(conferenceGame as boolean) as conference_game,
    cast(homeId as int) as home_id,
    homeTeam as home_team,
    homeConference as home_conference,
    homeClassification as home_classification,
    cast(homePoints as int) as home_points,
    cast(awayId as int) as away_id,
    awayTeam as away_team,
    awayConference as away_conference,
    awayClassification as away_classification,
    cast(awayPoints as int) as away_points,
    cast(venueId as int) as venue_id,
    venue
{%- endset -%}

{{ cfbd_union('games', projection) }}
