{{ config(alias='game_features') }}

/*
    One row per FBS-vs-FBS game: as-of features for both sides, market line fields, labels.

    "FBS-vs-FBS" is evaluated per season via silver_team_seasons, so a team's FCS years are
    excluded rather than backdated from today's membership.

    Market lines live here for the model-vs-market UI only. src/saturday_hq/ml/train.py
    deliberately excludes them from FEATURE_COLS.

    SP+/PPA come in two vintages. The _prior columns are last season's ratings and are what
    FEATURE_COLS uses; the unsuffixed ones are this season's, which for any finished season
    were computed from the game being predicted. See gold_team_week.

    Form comes in both flavours. FEATURE_COLS uses the _fbs columns, which ignore games
    against non-FBS opponents; the unsuffixed ones are the literal record, kept for
    reporting. See gold_team_week for why.

    The as-of join takes the newest team_week row STRICTLY BEFORE the game's week. The
    cutoff has to be exclusive: a team_week row for week W is cumulative through week W,
    so joining on week <= W hands the model the result of the very game it is predicting.
    Week-1 games therefore have null form, which the training pipeline imputes.
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
        tw.sp_overall_prior as home_sp_overall_prior,
        tw.sp_offense_prior as home_sp_offense_prior,
        tw.sp_defense_prior as home_sp_defense_prior,
        tw.ppa_offense_prior as home_ppa_offense_prior,
        tw.ppa_defense_prior as home_ppa_defense_prior,
        tw.talent as home_talent,
        tw.recruiting_points as home_recruiting_points,
        tw.win_pct as home_win_pct,
        tw.win_pct_fbs as home_win_pct_fbs,
        tw.avg_margin_l3 as home_avg_margin_l3,
        tw.avg_margin_l3_fbs as home_avg_margin_l3_fbs,
        tw.point_diff as home_point_diff,
        tw.games_played as home_games_played
    from games as g
    left join {{ ref('gold_team_week') }} as tw
        on tw.season = g.season
       and tw.team = g.home_team
       and tw.week < g.week
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
        tw.sp_overall_prior as away_sp_overall_prior,
        tw.sp_offense_prior as away_sp_offense_prior,
        tw.sp_defense_prior as away_sp_defense_prior,
        tw.ppa_offense_prior as away_ppa_offense_prior,
        tw.ppa_defense_prior as away_ppa_defense_prior,
        tw.talent as away_talent,
        tw.recruiting_points as away_recruiting_points,
        tw.win_pct as away_win_pct,
        tw.win_pct_fbs as away_win_pct_fbs,
        tw.avg_margin_l3 as away_avg_margin_l3,
        tw.avg_margin_l3_fbs as away_avg_margin_l3_fbs,
        tw.point_diff as away_point_diff,
        tw.games_played as away_games_played
    from games as g
    left join {{ ref('gold_team_week') }} as tw
        on tw.season = g.season
       and tw.team = g.away_team
       and tw.week < g.week
    qualify row_number() over (
        partition by g.game_id
        order by tw.week desc nulls last
    ) = 1

),

current_market as (

    select
        game_id,
        provider as line_provider,
        spread as market_spread,
        over_under as market_ou
    from {{ ref('silver_lines') }}

),

opening_market as (

    select
        game_id,
        provider as opening_line_provider,
        spread_open as market_spread_open,
        over_under_open as market_ou_open
    from {{ ref('silver_opening_lines') }}

),

moneyline_market as (

    select
        game_id,
        provider as moneyline_provider,
        home_moneyline as market_home_ml,
        away_moneyline as market_away_ml
    from {{ ref('silver_moneylines') }}

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
    om.* except (game_id),
    ml.* except (game_id),

    -- Raw conversion of the posted price, vig included: what a bettor actually sees.
    {{ american_ml_to_prob('ml.market_home_ml') }} as market_home_win_prob_implied,
    -- Overround removed, so it can be compared with a model probability. See no_vig_home_prob.
    {{ no_vig_home_prob('ml.market_home_ml', 'ml.market_away_ml') }} as market_home_win_prob_novig,

    hf.home_sp_overall - af.away_sp_overall as sp_overall_diff,
    hf.home_ppa_offense - af.away_ppa_offense as ppa_offense_diff,
    hf.home_ppa_defense - af.away_ppa_defense as ppa_defense_diff,
    hf.home_sp_overall_prior - af.away_sp_overall_prior as sp_overall_diff_prior,
    hf.home_ppa_offense_prior - af.away_ppa_offense_prior as ppa_offense_diff_prior,
    hf.home_ppa_defense_prior - af.away_ppa_defense_prior as ppa_defense_diff_prior,
    hf.home_talent - af.away_talent as talent_diff

from games as g
inner join {{ ref('silver_team_seasons') }} as home_fbs
    on home_fbs.season = g.season
   and home_fbs.team = g.home_team
inner join {{ ref('silver_team_seasons') }} as away_fbs
    on away_fbs.season = g.season
   and away_fbs.team = g.away_team
left join home_form as hf
    on hf.game_id = g.game_id
left join away_form as af
    on af.game_id = g.game_id
left join current_market as m
    on m.game_id = g.game_id
left join opening_market as om
    on om.game_id = g.game_id
left join moneyline_market as ml
    on ml.game_id = g.game_id
