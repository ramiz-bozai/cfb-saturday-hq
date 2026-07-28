{{ config(alias='game_features') }}

/*
    One row per FBS-vs-FBS game: as-of features for both sides, market line fields, labels.

    Market lines live here for the model-vs-market UI only. src/saturday_hq/ml/train.py
    deliberately excludes them from FEATURE_COLS.

    The as-of join takes the newest team_week row at or before the game's week, so a
    game is never described using form recorded after it was played.
*/

with games as (

    select *
    from {{ ref('silver_games') }}

),

home_form as (

    select
        g.game_id,
        tw.week as home_feature_week,
        tw.sp_overall as home_sp_overall,
        tw.sp_offense as home_sp_offense,
        tw.sp_defense as home_sp_defense,
        tw.ppa_offense as home_ppa_offense,
        tw.ppa_defense as home_ppa_defense,
        tw.talent as home_talent,
        tw.recruiting_points as home_recruiting_points,
        tw.win_pct as home_win_pct,
        tw.avg_margin_l3 as home_avg_margin_l3,
        tw.point_diff as home_point_diff,
        tw.games_played as home_games_played
    from games as g
    left join {{ ref('gold_team_week') }} as tw
        on tw.season = g.season
       and tw.team = g.home_team
       and tw.week <= g.week
    qualify row_number() over (
        partition by g.game_id
        order by tw.week desc nulls last
    ) = 1

),

away_form as (

    select
        g.game_id,
        tw.week as away_feature_week,
        tw.sp_overall as away_sp_overall,
        tw.sp_offense as away_sp_offense,
        tw.sp_defense as away_sp_defense,
        tw.ppa_offense as away_ppa_offense,
        tw.ppa_defense as away_ppa_defense,
        tw.talent as away_talent,
        tw.recruiting_points as away_recruiting_points,
        tw.win_pct as away_win_pct,
        tw.avg_margin_l3 as away_avg_margin_l3,
        tw.point_diff as away_point_diff,
        tw.games_played as away_games_played
    from games as g
    left join {{ ref('gold_team_week') }} as tw
        on tw.season = g.season
       and tw.team = g.away_team
       and tw.week <= g.week
    qualify row_number() over (
        partition by g.game_id
        order by tw.week desc nulls last
    ) = 1

),

market as (

    select
        game_id,
        provider as line_provider,
        spread as market_spread,
        spread_open as market_spread_open,
        over_under as market_ou,
        home_moneyline as market_home_ml,
        away_moneyline as market_away_ml
    from {{ ref('silver_lines') }}

)

select
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.start_date,
    g.completed,
    g.neutral_site,
    g.home_team,
    g.away_team,
    g.home_conference,
    g.away_conference,
    g.home_points,
    g.away_points,
    g.home_won,
    g.margin_home,
    g.total_points,

    hf.* except (game_id),
    af.* except (game_id),
    m.* except (game_id),

    {{ american_ml_to_prob('m.market_home_ml') }} as market_home_win_prob_implied,

    hf.home_sp_overall - af.away_sp_overall as sp_overall_diff,
    hf.home_ppa_offense - af.away_ppa_offense as ppa_offense_diff,
    hf.home_ppa_defense - af.away_ppa_defense as ppa_defense_diff,
    hf.home_talent - af.away_talent as talent_diff

from games as g
inner join {{ ref('silver_teams') }} as home_fbs
    on home_fbs.team = g.home_team
inner join {{ ref('silver_teams') }} as away_fbs
    on away_fbs.team = g.away_team
left join home_form as hf
    on hf.game_id = g.game_id
left join away_form as af
    on af.game_id = g.game_id
left join market as m
    on m.game_id = g.game_id
