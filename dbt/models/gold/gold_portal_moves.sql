{{ config(alias='portal_moves') }}

/*
    Transfer portal rows enriched with prior-season usage/production at the origin school.

    Impact / projected starter:
      - OL/ST: talent (≥0.85 / ≥0.90) or stars (≥3 / ≥4)
      - Skill/defense with prior stats: usage/production gates
      - Missing prior: talent fallback, else impact_class = unknown (not auto-depth)

    talent_score prefers transfer_rating, then prior recruiting rating, then stars/5.
*/

with origin_roster as (

    select
        season + 1 as portal_season,
        team as origin_team,
        player_name_key,
        athlete_id,
        first_name || ' ' || last_name as player_name,
        position_group
    from {{ ref('silver_rosters') }}

),

prior_prod as (

    select *
    from {{ ref('gold_player_season') }}

),

portal as (

    select *
    from {{ ref('silver_player_portal') }}

)

select
    p.season,
    p.first_name,
    p.last_name,
    p.player_name_key,
    p.position,
    p.position_group,
    p.origin,
    p.destination,
    p.transfer_date,
    p.transfer_rating,
    cast(p.transfer_stars as int) as transfer_stars,
    p.eligibility,
    o.athlete_id,
    coalesce(ps.usage_overall, 0.0) as prior_usage_overall,
    coalesce(ps.total_ppa_all, 0.0) as prior_total_ppa,
    coalesce(ps.production_score, 0.0) as prior_production_score,
    cast(ps.stars as int) as prior_stars,
    ps.recruiting_rating as prior_recruiting_rating,
    cast(round(ps.pass_att) as int) as prior_pass_att,
    cast(round(ps.pass_yds) as int) as prior_pass_yds,
    cast(round(ps.rush_yds) as int) as prior_rush_yds,
    cast(round(ps.rec_yds) as int) as prior_rec_yds,
    cast(round(ps.tackles) as int) as prior_tackles,
    ps.tfl as prior_tfl,
    ps.sacks as prior_sacks,
    cast(round(ps.interceptions) as int) as prior_interceptions,
    cast(round(ps.kick_points) as int) as prior_kick_points,
    coalesce(
        p.transfer_rating,
        ps.recruiting_rating,
        cast(p.transfer_stars as double) / 5.0,
        cast(ps.stars as double) / 5.0,
        0.0
    ) as talent_score,
    {{ preview_impact_class(
        'p.position_group',
        'ps.usage_overall',
        'ps.production_score',
        "coalesce(p.transfer_rating, ps.recruiting_rating, cast(p.transfer_stars as double) / 5.0, cast(ps.stars as double) / 5.0)",
        'coalesce(p.transfer_stars, ps.stars)',
        'ps.athlete_id is not null'
    ) }} as impact_class,
    {{ preview_projected_starter(
        'p.position_group',
        'ps.usage_overall',
        'ps.production_score',
        "coalesce(p.transfer_rating, ps.recruiting_rating, cast(p.transfer_stars as double) / 5.0, cast(ps.stars as double) / 5.0)",
        'coalesce(p.transfer_stars, ps.stars)',
        'ps.athlete_id is not null'
    ) }} as projected_starter
from portal as p
left join origin_roster as o
    on o.portal_season = p.season
   and o.origin_team = p.origin
   and o.player_name_key = p.player_name_key
left join prior_prod as ps
    on ps.season = p.season - 1
   and ps.athlete_id = o.athlete_id
   and ps.team = p.origin
