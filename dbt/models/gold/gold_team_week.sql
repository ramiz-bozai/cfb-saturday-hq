{{ config(alias='team_week') }}

/*
    One row per team-season-season_type-week: as-of form from completed games plus season SP+/PPA.
    Running windows use start_date, not week, because postseason week numbers restart at 1.

    SP+/PPA from the CFBD team endpoints are season aggregates, so the same season value
    is attached to every week; the rolling columns are what actually change week to week.

    Those aggregates come in two vintages, and the distinction matters:

    - sp_* / ppa_* are THIS season's ratings. For a finished season they are computed from
      every game in it, including whichever game you are looking at, so they are correct for
      reporting ("what was this team's 2019 SP+") and unusable as model features.
    - sp_*_prior / ppa_*_prior are last season's, known before a snap is played. These are
      what FEATURE_COLS uses.

    talent and recruiting need no such split: signing day precedes the season, so the current
    season's values are legitimately known in advance.

    Two flavours of form, on purpose:

    - wins / losses / win_pct / point_diff / avg_margin_l3 count EVERY completed game,
      including the one or two FCS opponents most teams schedule. These are the literal
      record and are what Genie and any reporting surface should use.
    - win_pct_fbs / avg_margin_l3_fbs count FBS opponents only. Margins against non-FBS
      teams average roughly double (~30 vs ~16 points), so including them makes form
      incomparable between a team that just played an FCS opponent and one that did not.
      These are the versions FEATURE_COLS feeds to the model.
*/

with completed_games as (

    select *
    from {{ ref('silver_games') }}
    where completed

),

team_games as (

    select
        season,
        season_type,
        week,
        start_date,
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
        season_type,
        week,
        start_date,
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
        t.is_notre_dame,
        opp.team is not null as opp_is_fbs
    -- Season-grained on purpose: silver_teams would apply today's membership and conferences to
    -- every historical season, which both mislabels pre-realignment conferences and counts the
    -- FCS years of later FBS movers as FBS.
    from team_games as tg
    inner join {{ ref('silver_team_seasons') }} as t
        on t.season = tg.season
       and t.team = tg.team
    left join {{ ref('silver_team_seasons') }} as opp
        on opp.season = tg.season
       and opp.team = tg.opponent

),

running as (

    select
        *,
        count(*) over w_season as games_played,
        sum(case when won then 1 else 0 end) over w_season as wins,
        sum(points_for - points_against) over w_season as point_diff,
        avg(points_for - points_against) over w_last3 as avg_margin_l3,
        sum(case when opp_is_fbs then 1 else 0 end) over w_season as fbs_games_played,
        sum(case when opp_is_fbs and won then 1 else 0 end) over w_season as fbs_wins
    from fbs_team_games
    window
        w_season as (
            partition by season, team
            order by start_date, game_id
            rows between unbounded preceding and current row
        ),
        w_last3 as (
            partition by season, team
            order by start_date, game_id
            rows between 2 preceding and current row
        )

),

latest_per_week as (

    select
        *,
        games_played - wins as losses,
        wins / games_played as win_pct,
        fbs_wins / nullif(fbs_games_played, 0) as win_pct_fbs
    from running
    qualify row_number() over (
        partition by season, team, season_type, week
        order by start_date desc, game_id desc
    ) = 1

),

-- Last three FBS games, not "the FBS games among the last three": the window runs over a
-- sequence with non-FBS opponents already removed.
fbs_only_form as (

    select
        season,
        season_type,
        team,
        week,
        start_date,
        game_id,
        avg(points_for - points_against) over (
            partition by season, team
            order by start_date, game_id
            rows between 2 preceding and current row
        ) as avg_margin_l3_fbs
    from fbs_team_games
    where opp_is_fbs

),

-- As-of join, same pattern game_features uses: newest FBS game at or before this game timestamp.
fbs_form_asof as (

    select
        f.season,
        f.season_type,
        f.team,
        f.week,
        f.start_date,
        ff.avg_margin_l3_fbs
    from latest_per_week as f
    left join fbs_only_form as ff
        on ff.season = f.season
       and ff.team = f.team
       and ff.start_date <= f.start_date
    qualify row_number() over (
        partition by f.season, f.team, f.season_type, f.week
        order by ff.start_date desc nulls last, ff.game_id desc nulls last
    ) = 1

)

select
    f.season,
    f.season_type,
    f.week,
    f.start_date,
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
    f.fbs_games_played,
    f.fbs_wins,
    f.win_pct_fbs,
    ff.avg_margin_l3_fbs,
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
    sp_prior.sp_overall as sp_overall_prior,
    sp_prior.sp_offense as sp_offense_prior,
    sp_prior.sp_defense as sp_defense_prior,
    ppa_prior.ppa_offense as ppa_offense_prior,
    ppa_prior.ppa_defense as ppa_defense_prior,
    talent.talent,
    recruiting.recruiting_rank,
    recruiting.recruiting_points,
    {{ conference_group('f.conference', 'f.is_notre_dame') }} as conference_group
from latest_per_week as f
left join fbs_form_asof as ff
    on ff.season = f.season
   and ff.season_type = f.season_type
   and ff.team = f.team
   and ff.week = f.week
left join {{ ref('silver_sp_plus') }} as sp
    on sp.season = f.season and sp.team = f.team
left join {{ ref('silver_ppa_teams') }} as ppa
    on ppa.season = f.season and ppa.team = f.team
-- Last season's ratings, the only vintage that is knowable before this season's games.
left join {{ ref('silver_sp_plus') }} as sp_prior
    on sp_prior.season = f.season - 1 and sp_prior.team = f.team
left join {{ ref('silver_ppa_teams') }} as ppa_prior
    on ppa_prior.season = f.season - 1 and ppa_prior.team = f.team
left join {{ ref('silver_talent') }} as talent
    on talent.season = f.season and talent.team = f.team
left join {{ ref('silver_recruiting_teams') }} as recruiting
    on recruiting.season = f.season and recruiting.team = f.team
