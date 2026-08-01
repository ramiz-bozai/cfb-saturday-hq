{{ config(alias='player_season') }}

/*
    One row per athlete-season-team: usage, PPA, key box stats, recruiting profile.
    Grain for Season Preview production weighting.

    usage_overall:
      - Offense: CFBD /player/usage play share (when present).
      - DL/LB/DB: share of that team's tackle-weighted defense production
        (tackles + 2*(TFL − sacks) + 3*sacks + 2*INT). Not snap share — CFBD has none.
        TFL includes sacks in CFBD; non-sack TFLs and sacks are weighted separately.
      - OL/ST: null (no usable proxy in this data).
*/

with stats_wide as (

    select
        season,
        athlete_id,
        team,
        max(player_name) as player_name,
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
        cast(max(stars) as int) as stars,
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
        -- Usage/PPA cover offense; season stats cover defense/ST/OL. Never leave name null when
        -- any source has it — stats_wide was previously omitted and left ~2/3 of rows unnamed.
        coalesce(
            nullif(trim(u.player_name), ''),
            nullif(trim(p.player_name), ''),
            nullif(trim(s.player_name), '')
        ) as player_name,
        coalesce(u.position, p.position, s.position) as position,
        coalesce(u.position_group, p.position_group, s.position_group) as position_group,
        coalesce(u.team, p.team, s.team) as team,
        coalesce(u.conference, p.conference) as conference,
        u.usage_overall as cfbd_usage_overall,
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

),

enriched as (

    select
        b.* except (player_name),
        coalesce(
            nullif(trim(b.player_name), ''),
            nullif(trim(concat_ws(' ', rost.first_name, rost.last_name)), '')
        ) as player_name,
        coalesce(b.position, rost.position) as position_final,
        coalesce(b.position_group, rost.position_group) as position_group_final,
        case
            when coalesce(b.position_group, rost.position_group) in ('DL', 'LB', 'DB')
            then {{ defense_production_score('b.tackles', 'b.tfl', 'b.sacks', 'b.interceptions') }}
            else 0.0
        end as defense_prod,
        r.stars,
        r.recruiting_rating,
        r.recruiting_rank,
        r.recruiting_committed_to,
        r.recruiting_class_year
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

),

with_team_def as (

    select
        e.*,
        sum(e.defense_prod) over (partition by e.season, e.team) as team_defense_prod
    from enriched as e

)

select
    season,
    athlete_id,
    player_name,
    position_final as position,
    position_group_final as position_group,
    team,
    conference,
    -- CFBD offensive usage when present; else DL/LB/DB share of team defense production.
    coalesce(
        cfbd_usage_overall,
        case
            when position_group_final in ('DL', 'LB', 'DB')
             and team_defense_prod > 0
            then defense_prod / team_defense_prod
        end
    ) as usage_overall,
    usage_pass,
    usage_rush,
    avg_ppa_all,
    avg_ppa_pass,
    avg_ppa_rush,
    total_ppa_all,
    total_ppa_pass,
    total_ppa_rush,
    cast(round(pass_att) as int) as pass_att,
    cast(round(pass_yds) as int) as pass_yds,
    cast(round(pass_td) as int) as pass_td,
    cast(round(pass_int) as int) as pass_int,
    cast(round(rush_att) as int) as rush_att,
    cast(round(rush_yds) as int) as rush_yds,
    cast(round(rush_td) as int) as rush_td,
    cast(round(receptions) as int) as receptions,
    cast(round(rec_yds) as int) as rec_yds,
    cast(round(rec_td) as int) as rec_td,
    cast(round(tackles) as int) as tackles,
    tfl,
    sacks,
    cast(round(interceptions) as int) as interceptions,
    cast(round(fg_made) as int) as fg_made,
    cast(round(fg_att) as int) as fg_att,
    cast(round(kick_points) as int) as kick_points,
    cast(round(fumbles_lost) as int) as fumbles_lost,
    cast(stars as int) as stars,
    recruiting_rating,
    recruiting_rank,
    recruiting_committed_to,
    recruiting_class_year,
    -- Production: offense PPA (else CFBD usage×50); defense absolute tackle-weighted score.
    -- Do not use synthetic defensive usage×50 here — that would crush real tackle scores.
    coalesce(
        total_ppa_all,
        cfbd_usage_overall * 50.0,
        case
            when position_group_final in ('DL', 'LB', 'DB') then defense_prod
        end,
        0.0
    ) as production_score,
    coalesce(recruiting_rating, cast(stars as double) / 5.0) as talent_score
from with_team_def
where nullif(trim(player_name), '') is not null
