{{ config(alias='team_week') }}

/*
    One row per team-season-week: as-of form from completed games plus season SP+/PPA.

    SP+/PPA from the CFBD team endpoints are season aggregates, so the same season value
    is attached to every week; the rolling columns are what actually change week to week.
*/

with completed_games as (

    select *
    from {{ ref('silver_games') }}
    where completed

),

team_games as (

    select
        season,
        week,
        game_id,
        home_team as team,
        away_team as opponent,
        true as is_home,
        home_points as points_for,
        away_points as points_against,
        home_points > away_points as won
    from completed_games

    union all

    select
        season,
        week,
        game_id,
        away_team as team,
        home_team as opponent,
        false as is_home,
        away_points as points_for,
        home_points as points_against,
        away_points > home_points as won
    from completed_games

),

fbs_team_games as (

    select
        tg.*,
        t.conference,
        t.is_notre_dame
    from team_games as tg
    inner join {{ ref('silver_teams') }} as t
        on t.team = tg.team

),

running as (

    select
        *,
        count(*) over w_season as games_played,
        sum(case when won then 1 else 0 end) over w_season as wins,
        sum(points_for - points_against) over w_season as point_diff,
        avg(points_for - points_against) over w_last3 as avg_margin_l3
    from fbs_team_games
    window
        w_season as (
            partition by season, team
            order by week, game_id
            rows between unbounded preceding and current row
        ),
        w_last3 as (
            partition by season, team
            order by week, game_id
            rows between 2 preceding and current row
        )

),

latest_per_week as (

    select
        *,
        games_played - wins as losses,
        wins / games_played as win_pct
    from running
    qualify row_number() over (
        partition by season, team, week
        order by game_id desc
    ) = 1

)

select
    f.season,
    f.week,
    f.game_id,
    f.team,
    f.opponent,
    f.is_home,
    f.points_for,
    f.points_against,
    f.won,
    f.conference,
    f.is_notre_dame,
    f.games_played,
    f.wins,
    f.losses,
    f.win_pct,
    f.point_diff,
    f.avg_margin_l3,
    sp.sp_overall,
    sp.sp_rank,
    sp.sp_offense,
    sp.sp_defense,
    sp.sp_special_teams,
    sp.sp_sos,
    ppa.ppa_offense,
    ppa.ppa_defense,
    ppa.ppa_offense_passing,
    ppa.ppa_offense_rushing,
    ppa.ppa_defense_passing,
    ppa.ppa_defense_rushing,
    talent.talent,
    recruiting.recruiting_rank,
    recruiting.recruiting_points,
    {{ conference_group('f.conference', 'f.is_notre_dame') }} as conference_group
from latest_per_week as f
left join {{ ref('silver_sp_plus') }} as sp
    on sp.season = f.season and sp.team = f.team
left join {{ ref('silver_ppa_teams') }} as ppa
    on ppa.season = f.season and ppa.team = f.team
left join {{ ref('silver_talent') }} as talent
    on talent.season = f.season and talent.team = f.team
left join {{ ref('silver_recruiting_teams') }} as recruiting
    on recruiting.season = f.season and recruiting.team = f.team
