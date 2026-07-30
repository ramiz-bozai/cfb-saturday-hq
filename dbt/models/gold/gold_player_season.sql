{{ config(alias='player_season') }}

/*
    One row per athlete-season-team: usage, PPA, key box stats, recruiting profile.
    Grain for Offseason Preview production weighting.
*/

with stats_wide as (

    select
        season,
        athlete_id,
        team,
        max(position) as position,
        max(position_group) as position_group,
        max(case when category = 'passing' and stat_type = 'ATT' then stat_value end) as pass_att,
        max(case when category = 'passing' and stat_type = 'YDS' then stat_value end) as pass_yds,
        max(case when category = 'passing' and stat_type = 'TD' then stat_value end) as pass_td,
        max(case when category = 'passing' and stat_type = 'INT' then stat_value end) as pass_int,
        max(case when category = 'rushing' and stat_type = 'CAR' then stat_value end) as rush_att,
        max(case when category = 'rushing' and stat_type = 'YDS' then stat_value end) as rush_yds,
        max(case when category = 'rushing' and stat_type = 'TD' then stat_value end) as rush_td,
        max(case when category = 'receiving' and stat_type = 'REC' then stat_value end) as receptions,
        max(case when category = 'receiving' and stat_type = 'YDS' then stat_value end) as rec_yds,
        max(case when category = 'receiving' and stat_type = 'TD' then stat_value end) as rec_td,
        max(case when category = 'defensive' and stat_type = 'TOT' then stat_value end) as tackles,
        max(case when category = 'defensive' and stat_type = 'TFL' then stat_value end) as tfl,
        max(case when category = 'defensive' and stat_type = 'SACKS' then stat_value end) as sacks,
        max(case when category = 'interceptions' and stat_type = 'INT' then stat_value end) as interceptions,
        max(case when category = 'kicking' and stat_type = 'FGM' then stat_value end) as fg_made,
        max(case when category = 'kicking' and stat_type = 'FGA' then stat_value end) as fg_att,
        max(case when category = 'kicking' and stat_type = 'PTS' then stat_value end) as kick_points,
        max(case when category = 'fumbles' and stat_type = 'LOST' then stat_value end) as fumbles_lost
    from {{ ref('silver_player_season_stats') }}
    group by season, athlete_id, team

),

recruiting as (

    select
        athlete_id,
        max(stars) as stars,
        max(rating) as recruiting_rating,
        min(recruiting_rank) as recruiting_rank,
        max_by(committed_to, class_year) as recruiting_committed_to,
        max(class_year) as recruiting_class_year
    from {{ ref('silver_recruiting_players') }}
    where athlete_id is not null
    group by athlete_id

),

base as (

    select
        coalesce(u.season, p.season, s.season) as season,
        coalesce(u.athlete_id, p.athlete_id, s.athlete_id) as athlete_id,
        coalesce(u.player_name, p.player_name) as player_name,
        coalesce(u.position, p.position, s.position) as position,
        coalesce(u.position_group, p.position_group, s.position_group) as position_group,
        coalesce(u.team, p.team, s.team) as team,
        coalesce(u.conference, p.conference) as conference,
        u.usage_overall,
        u.usage_pass,
        u.usage_rush,
        p.avg_ppa_all,
        p.avg_ppa_pass,
        p.avg_ppa_rush,
        p.total_ppa_all,
        p.total_ppa_pass,
        p.total_ppa_rush,
        s.pass_att,
        s.pass_yds,
        s.pass_td,
        s.pass_int,
        s.rush_att,
        s.rush_yds,
        s.rush_td,
        s.receptions,
        s.rec_yds,
        s.rec_td,
        s.tackles,
        s.tfl,
        s.sacks,
        s.interceptions,
        s.fg_made,
        s.fg_att,
        s.kick_points,
        s.fumbles_lost
    from {{ ref('silver_player_usage') }} as u
    full outer join {{ ref('silver_ppa_players_season') }} as p
        on p.season = u.season
       and p.athlete_id = u.athlete_id
       and p.team = u.team
    full outer join stats_wide as s
        on s.season = coalesce(u.season, p.season)
       and s.athlete_id = coalesce(u.athlete_id, p.athlete_id)
       and s.team = coalesce(u.team, p.team)

)

select
    b.season,
    b.athlete_id,
    b.player_name,
    coalesce(b.position, rost.position) as position,
    coalesce(b.position_group, rost.position_group) as position_group,
    b.team,
    b.conference,
    b.usage_overall,
    b.usage_pass,
    b.usage_rush,
    b.avg_ppa_all,
    b.avg_ppa_pass,
    b.avg_ppa_rush,
    b.total_ppa_all,
    b.total_ppa_pass,
    b.total_ppa_rush,
    b.pass_att,
    b.pass_yds,
    b.pass_td,
    b.pass_int,
    b.rush_att,
    b.rush_yds,
    b.rush_td,
    b.receptions,
    b.rec_yds,
    b.rec_td,
    b.tackles,
    b.tfl,
    b.sacks,
    b.interceptions,
    b.fg_made,
    b.fg_att,
    b.kick_points,
    b.fumbles_lost,
    r.stars,
    r.recruiting_rating,
    r.recruiting_rank,
    r.recruiting_committed_to,
    r.recruiting_class_year,
    -- Single production score for transfer weighting: total PPA when present, else usage.
    coalesce(b.total_ppa_all, b.usage_overall * 50.0, 0.0) as production_score,
    -- 0-1 talent score for portal net-talent ledgers (rating preferred, else stars/5).
    coalesce(r.recruiting_rating, cast(r.stars as double) / 5.0) as talent_score
from base as b
left join recruiting as r
    on r.athlete_id = b.athlete_id
left join {{ ref('silver_rosters') }} as rost
    on rost.season = b.season
   and rost.athlete_id = b.athlete_id
   and rost.team = b.team
where b.season is not null
  and b.athlete_id is not null
  and b.team is not null
