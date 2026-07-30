{{ config(alias='returning_production_team') }}

/*
    Team-level returning production for a preview season.

    Prefer CFBD /player/returning when present for that season. Otherwise compute from the
    constructed roster snapshot vs prior-season team totals.

    Offense returning = (pass_yds + rush_yds + rec_yds) returning / prior.
    Defense returning = weighted (tackles + 2*TFL + 3*sacks + 2*INT) returning / prior.
*/

with cfbd as (

    select *
    from {{ ref('silver_player_returning') }}

),

prior_team_totals as (

    select
        season,
        team,
        sum(coalesce(production_score, 0.0)) as production_score,
        sum(coalesce(usage_overall, 0.0)) as usage_overall,
        sum(coalesce(total_ppa_all, 0.0)) as total_ppa,
        sum(coalesce(total_ppa_pass, 0.0)) as total_passing_ppa,
        sum(coalesce(total_ppa_rush, 0.0)) as total_rushing_ppa,
        sum(coalesce(pass_att, 0.0)) as pass_att,
        sum(coalesce(pass_yds, 0.0)) as pass_yds,
        sum(coalesce(rush_yds, 0.0)) as rush_yds,
        sum(coalesce(rec_yds, 0.0)) as rec_yds,
        sum(coalesce(tackles, 0.0)) as tackles,
        sum(coalesce(tfl, 0.0)) as tfl,
        sum(coalesce(sacks, 0.0)) as sacks,
        sum(coalesce(interceptions, 0.0)) as interceptions,
        sum(coalesce(kick_points, 0.0)) as kick_points,
        sum(coalesce(pass_yds, 0.0) + coalesce(rush_yds, 0.0) + coalesce(rec_yds, 0.0)) as offense_yards,
        sum(
            coalesce(tackles, 0.0)
            + 2.0 * coalesce(tfl, 0.0)
            + 3.0 * coalesce(sacks, 0.0)
            + 2.0 * coalesce(interceptions, 0.0)
        ) as defense_weighted
    from {{ ref('gold_player_season') }}
    group by season, team

),

returning_on_roster as (

    select
        r.season,
        r.team,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_production_score, 0.0) else 0.0 end) as returning_production,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_usage_overall, 0.0) else 0.0 end) as returning_usage,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_total_ppa, 0.0) else 0.0 end) as returning_ppa,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_pass_att, 0.0) else 0.0 end) as returning_pass_att,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_pass_yds, 0.0) else 0.0 end) as returning_pass_yds,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_rush_yds, 0.0) else 0.0 end) as returning_rush_yds,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_rec_yds, 0.0) else 0.0 end) as returning_rec_yds,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_tackles, 0.0) else 0.0 end) as returning_tackles,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_tfl, 0.0) else 0.0 end) as returning_tfl,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_sacks, 0.0) else 0.0 end) as returning_sacks,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_interceptions, 0.0) else 0.0 end) as returning_interceptions,
        sum(case when not r.is_transfer_addition then coalesce(r.prior_kick_points, 0.0) else 0.0 end) as returning_kick_points
    from {{ ref('gold_roster_snapshot') }} as r
    group by r.season, r.team

),

computed as (

    select
        ret.season,
        ret.team,
        ts.conference,
        ret.returning_production / nullif(pt.production_score, 0) as percent_production,
        ret.returning_usage / nullif(pt.usage_overall, 0) as percent_usage,
        ret.returning_ppa / nullif(pt.total_ppa, 0) as percent_ppa,
        ret.returning_pass_yds / nullif(pt.pass_yds, 0) as percent_passing,
        ret.returning_pass_att / nullif(pt.pass_att, 0) as percent_passing_attempts,
        ret.returning_rush_yds / nullif(pt.rush_yds, 0) as percent_rushing,
        ret.returning_rec_yds / nullif(pt.rec_yds, 0) as percent_receiving,
        ret.returning_tackles / nullif(pt.tackles, 0) as percent_tackles,
        ret.returning_tfl / nullif(pt.tfl, 0) as percent_tfl,
        ret.returning_sacks / nullif(pt.sacks, 0) as percent_sacks,
        ret.returning_interceptions / nullif(pt.interceptions, 0) as percent_interceptions,
        ret.returning_kick_points / nullif(pt.kick_points, 0) as percent_kicking,
        (
            ret.returning_pass_yds + ret.returning_rush_yds + ret.returning_rec_yds
        ) / nullif(pt.offense_yards, 0) as percent_offense_returning,
        (
            ret.returning_tackles
            + 2.0 * ret.returning_tfl
            + 3.0 * ret.returning_sacks
            + 2.0 * ret.returning_interceptions
        ) / nullif(pt.defense_weighted, 0) as percent_defense_returning,
        ret.returning_production,
        ret.returning_usage,
        ret.returning_ppa
    from returning_on_roster as ret
    left join prior_team_totals as pt
        on pt.season = ret.season - 1
       and pt.team = ret.team
    left join {{ ref('silver_team_seasons') }} as ts
        on ts.team = ret.team
       and ts.season = ret.season - 1

)

select
    coalesce(c.season, x.season) as season,
    coalesce(c.team, x.team) as team,
    coalesce(c.conference, x.conference) as conference,
    coalesce(c.percent_ppa, x.percent_ppa) as percent_ppa,
    coalesce(c.percent_passing_ppa, x.percent_passing) as percent_passing_ppa,
    coalesce(c.percent_receiving_ppa, x.percent_receiving) as percent_receiving_ppa,
    coalesce(c.percent_rushing_ppa, x.percent_rushing) as percent_rushing_ppa,
    coalesce(c.usage, x.percent_usage) as percent_usage,
    coalesce(c.passing_usage, x.percent_passing_attempts) as percent_passing_usage,
    coalesce(c.receiving_usage, x.percent_receiving) as percent_receiving_usage,
    coalesce(c.rushing_usage, x.percent_rushing) as percent_rushing_usage,
    x.percent_production,
    x.percent_passing,
    x.percent_passing_attempts,
    x.percent_offense_returning,
    x.percent_defense_returning,
    x.percent_tackles,
    x.percent_tfl,
    x.percent_sacks,
    x.percent_interceptions,
    x.percent_kicking,
    x.returning_production,
    x.returning_usage,
    x.returning_ppa,
    case when c.team is not null then 'cfbd' else 'computed' end as source
from computed as x
full outer join cfbd as c
    on c.season = x.season
   and c.team = x.team
