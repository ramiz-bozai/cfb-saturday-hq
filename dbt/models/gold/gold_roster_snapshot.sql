{{ config(alias='roster_snapshot') }}

/*
    Roster for a target season.

    Prefer a published CFBD roster. When CFBD has not published one yet (typical before camp),
    construct it from the prior-season roster
      minus portal departures
      minus NFL draft picks (draft_year = target season)
      plus portal arrivals.
*/

with published_counts as (

    select season, team, count(*) as n_players
    from {{ ref('silver_rosters') }}
    group by season, team

),

published as (

    select
        season,
        team,
        athlete_id,
        first_name,
        last_name,
        player_name_key,
        position,
        position_group,
        class_year,
        jersey,
        'published' as roster_source,
        false as is_transfer_addition
    from {{ ref('silver_rosters') }}

),

prior_roster as (

    select
        season + 1 as season,
        team,
        athlete_id,
        first_name,
        last_name,
        player_name_key,
        position,
        position_group,
        class_year,
        jersey
    from {{ ref('silver_rosters') }}

),

departures as (

    select
        season,
        origin as team,
        player_name_key
    from {{ ref('silver_player_portal') }}
    where origin is not null
      and (destination is null or destination <> origin)

),

drafted as (

    select
        draft_year as season,
        athlete_id
    from {{ ref('silver_draft_picks') }}
    where athlete_id is not null

),

retained as (

    select
        p.season,
        p.team,
        p.athlete_id,
        p.first_name,
        p.last_name,
        p.player_name_key,
        p.position,
        p.position_group,
        p.class_year,
        p.jersey,
        'constructed' as roster_source,
        false as is_transfer_addition
    from prior_roster as p
    left join departures as d
        on d.season = p.season
       and d.team = p.team
       and d.player_name_key = p.player_name_key
    left join drafted as nfl
        on nfl.season = p.season
       and nfl.athlete_id = p.athlete_id
    where d.player_name_key is null
      and nfl.athlete_id is null

),

arrivals as (

    select
        m.season,
        m.destination as team,
        m.athlete_id,
        m.first_name,
        m.last_name,
        m.player_name_key,
        m.position,
        m.position_group,
        cast(null as int) as class_year,
        cast(null as int) as jersey,
        'constructed' as roster_source,
        true as is_transfer_addition
    from {{ ref('gold_portal_moves') }} as m
    where m.destination is not null

),

constructed as (

    select * from retained
    union all
    select * from arrivals

),

target_teams as (

    select distinct season, team from published
    union
    select distinct season, team from constructed

),

chosen as (

    select
        t.season,
        t.team,
        coalesce(p.athlete_id, c.athlete_id) as athlete_id,
        coalesce(p.first_name, c.first_name) as first_name,
        coalesce(p.last_name, c.last_name) as last_name,
        coalesce(p.player_name_key, c.player_name_key) as player_name_key,
        coalesce(p.position, c.position) as position,
        coalesce(p.position_group, c.position_group) as position_group,
        coalesce(p.class_year, c.class_year) as class_year,
        coalesce(p.jersey, c.jersey) as jersey,
        case
            when coalesce(pc.n_players, 0) > 0 then 'published'
            else 'constructed'
        end as roster_source,
        case
            when coalesce(pc.n_players, 0) > 0 then false
            else coalesce(c.is_transfer_addition, false)
        end as is_transfer_addition
    from target_teams as t
    left join published_counts as pc
        on pc.season = t.season
       and pc.team = t.team
    left join published as p
        on coalesce(pc.n_players, 0) > 0
       and p.season = t.season
       and p.team = t.team
    left join constructed as c
        on coalesce(pc.n_players, 0) = 0
       and c.season = t.season
       and c.team = t.team

)

select
    c.season,
    c.team,
    c.athlete_id,
    c.first_name,
    c.last_name,
    c.player_name_key,
    c.position,
    c.position_group,
    c.class_year,
    c.jersey,
    c.roster_source,
    c.is_transfer_addition,
    ps.usage_overall as prior_usage_overall,
    ps.total_ppa_all as prior_total_ppa,
    ps.production_score as prior_production_score,
    ps.avg_ppa_all as prior_avg_ppa,
    cast(round(ps.pass_att) as int) as prior_pass_att,
    cast(round(ps.pass_yds) as int) as prior_pass_yds,
    cast(round(ps.rush_yds) as int) as prior_rush_yds,
    cast(round(ps.rush_att) as int) as prior_rush_att,
    cast(round(ps.rec_yds) as int) as prior_rec_yds,
    cast(round(ps.tackles) as int) as prior_tackles,
    ps.tfl as prior_tfl,
    ps.sacks as prior_sacks,
    cast(round(ps.interceptions) as int) as prior_interceptions,
    cast(round(ps.kick_points) as int) as prior_kick_points,
    cast(round(ps.pass_int) as int) as prior_pass_int,
    cast(round(ps.fumbles_lost) as int) as prior_fumbles_lost,
    cast(ps.stars as int) as stars,
    ps.recruiting_rating,
    ps.talent_score as prior_talent_score
from chosen as c
left join {{ ref('gold_player_season') }} as ps
    on ps.athlete_id = c.athlete_id
   and ps.season = c.season - 1
where c.player_name_key is not null
   or c.athlete_id is not null
