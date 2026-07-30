{{ config(alias='replacement_risk') }}

/*
    Category-aware replacement risk callouts for the Preview tab.

    Departed production = portal exits + NFL draft picks (draft year = preview season).
    Primary metric by position group:
      QB → prior pass attempts
      WR/TE → receiving yards
      RB → rushing yards
      DL → sacks (EDGE stays inside DL)
      LB → tackles
      DB → interceptions (tackles fallback when INT thin)
      ST → kick points
      OL → production score
*/

with continuity as (

    select *
    from {{ ref('gold_unit_continuity') }}

),

prior_group_metrics as (

    select
        season,
        team,
        position_group,
        sum(coalesce(pass_att, 0.0)) as pass_att,
        sum(coalesce(rec_yds, 0.0)) as rec_yds,
        sum(coalesce(rush_yds, 0.0)) as rush_yds,
        sum(coalesce(sacks, 0.0)) as sacks,
        sum(coalesce(tfl, 0.0)) as tfl,
        sum(coalesce(tackles, 0.0)) as tackles,
        sum(coalesce(interceptions, 0.0)) as interceptions,
        sum(coalesce(kick_points, 0.0)) as kick_points,
        sum(coalesce(production_score, 0.0)) as production_score
    from {{ ref('gold_player_season') }}
    where position_group not in ('OTHER')
    group by season, team, position_group

),

portal_departed as (

    select
        season,
        origin as team,
        position_group,
        coalesce(prior_pass_att, 0.0) as prior_pass_att,
        coalesce(prior_rec_yds, 0.0) as prior_rec_yds,
        coalesce(prior_rush_yds, 0.0) as prior_rush_yds,
        coalesce(prior_sacks, 0.0) as prior_sacks,
        coalesce(prior_tfl, 0.0) as prior_tfl,
        coalesce(prior_tackles, 0.0) as prior_tackles,
        coalesce(prior_interceptions, 0.0) as prior_interceptions,
        coalesce(prior_kick_points, 0.0) as prior_kick_points,
        coalesce(prior_production_score, 0.0) as prior_production_score,
        athlete_id
    from {{ ref('gold_portal_moves') }}
    where origin is not null
      and (destination is null or destination <> origin)

),

draft_departed as (

    select
        d.draft_year as season,
        coalesce(ps.team, d.college_team) as team,
        coalesce(ps.position_group, d.position_group) as position_group,
        coalesce(ps.pass_att, 0.0) as prior_pass_att,
        coalesce(ps.rec_yds, 0.0) as prior_rec_yds,
        coalesce(ps.rush_yds, 0.0) as prior_rush_yds,
        coalesce(ps.sacks, 0.0) as prior_sacks,
        coalesce(ps.tfl, 0.0) as prior_tfl,
        coalesce(ps.tackles, 0.0) as prior_tackles,
        coalesce(ps.interceptions, 0.0) as prior_interceptions,
        coalesce(ps.kick_points, 0.0) as prior_kick_points,
        coalesce(ps.production_score, 0.0) as prior_production_score,
        d.athlete_id
    from {{ ref('silver_draft_picks') }} as d
    left join {{ ref('gold_player_season') }} as ps
        on ps.athlete_id = d.athlete_id
       and ps.season = d.draft_year - 1
    where d.athlete_id is not null
      -- Avoid double-count when a draftee also appears as a portal departure.
      and not exists (
          select 1
          from portal_departed as p
          where p.season = d.draft_year
            and p.athlete_id = d.athlete_id
      )

),

departed_metrics as (

    select
        season,
        team,
        position_group,
        sum(prior_pass_att) as departed_pass_att,
        sum(prior_rec_yds) as departed_rec_yds,
        sum(prior_rush_yds) as departed_rush_yds,
        sum(prior_sacks) as departed_sacks,
        sum(prior_tfl) as departed_tfl,
        sum(prior_tackles) as departed_tackles,
        sum(prior_interceptions) as departed_interceptions,
        sum(prior_kick_points) as departed_kick_points,
        sum(prior_production_score) as departed_production
    from (
        select * from portal_departed
        union all
        select * from draft_departed
    )
    where position_group not in ('OTHER')
      and team is not null
    group by season, team, position_group

),

best_returner as (

    select
        season,
        team,
        position_group,
        first_name || ' ' || last_name as best_returner,
        prior_production_score as best_returner_production,
        prior_pass_att as best_returner_pass_att,
        prior_rec_yds as best_returner_rec_yds,
        prior_rush_yds as best_returner_rush_yds,
        prior_sacks as best_returner_sacks,
        prior_tfl as best_returner_tfl,
        prior_tackles as best_returner_tackles,
        prior_interceptions as best_returner_interceptions,
        prior_kick_points as best_returner_kick_points
    from {{ ref('gold_roster_snapshot') }}
    where not is_transfer_addition
    qualify row_number() over (
        partition by season, team, position_group
        order by
            case position_group
                when 'QB' then coalesce(prior_pass_att, 0)
                when 'WR/TE' then coalesce(prior_rec_yds, 0)
                when 'RB' then coalesce(prior_rush_yds, 0)
                when 'DL' then coalesce(prior_sacks, 0)
                when 'LB' then coalesce(prior_tackles, 0)
                when 'DB' then coalesce(prior_interceptions, 0) * 10 + coalesce(prior_tackles, 0)
                when 'ST' then coalesce(prior_kick_points, 0)
                else coalesce(prior_production_score, 0)
            end desc
    ) = 1

),

enriched as (

    select
        c.season,
        c.team,
        c.position_group,
        c.replacement_risk,
        c.production_returning_pct,
        c.usage_returning_pct,
        c.impact_losses,
        c.impact_additions,
        c.projected_starters_lost,
        c.projected_starters_added,
        c.continuity_score,
        b.best_returner,
        case c.position_group
            when 'QB' then 'pass_att'
            when 'WR/TE' then 'rec_yds'
            when 'RB' then 'rush_yds'
            when 'DL' then 'sacks'
            when 'LB' then 'tackles'
            when 'DB' then case
                when coalesce(pg.interceptions, 0) >= 2 then 'interceptions'
                else 'tackles'
            end
            when 'ST' then 'kick_points'
            else 'production_score'
        end as metric_name,
        case c.position_group
            when 'QB' then coalesce(d.departed_pass_att, 0)
            when 'WR/TE' then coalesce(d.departed_rec_yds, 0)
            when 'RB' then coalesce(d.departed_rush_yds, 0)
            when 'DL' then coalesce(d.departed_sacks, 0)
            when 'LB' then coalesce(d.departed_tackles, 0)
            when 'DB' then case
                when coalesce(pg.interceptions, 0) >= 2 then coalesce(d.departed_interceptions, 0)
                else coalesce(d.departed_tackles, 0)
            end
            when 'ST' then coalesce(d.departed_kick_points, 0)
            else coalesce(d.departed_production, 0)
        end as departed_metric,
        case c.position_group
            when 'QB' then coalesce(pg.pass_att, 0)
            when 'WR/TE' then coalesce(pg.rec_yds, 0)
            when 'RB' then coalesce(pg.rush_yds, 0)
            when 'DL' then coalesce(pg.sacks, 0)
            when 'LB' then coalesce(pg.tackles, 0)
            when 'DB' then case
                when coalesce(pg.interceptions, 0) >= 2 then coalesce(pg.interceptions, 0)
                else coalesce(pg.tackles, 0)
            end
            when 'ST' then coalesce(pg.kick_points, 0)
            else coalesce(pg.production_score, 0)
        end as prior_metric,
        case c.position_group
            when 'QB' then coalesce(b.best_returner_pass_att, 0)
            when 'WR/TE' then coalesce(b.best_returner_rec_yds, 0)
            when 'RB' then coalesce(b.best_returner_rush_yds, 0)
            when 'DL' then coalesce(b.best_returner_sacks, 0)
            when 'LB' then coalesce(b.best_returner_tackles, 0)
            when 'DB' then case
                when coalesce(pg.interceptions, 0) >= 2 then coalesce(b.best_returner_interceptions, 0)
                else coalesce(b.best_returner_tackles, 0)
            end
            when 'ST' then coalesce(b.best_returner_kick_points, 0)
            else coalesce(b.best_returner_production, 0)
        end as best_returner_metric
    from continuity as c
    left join prior_group_metrics as pg
        on pg.season = c.season - 1
       and pg.team = c.team
       and pg.position_group = c.position_group
    left join departed_metrics as d
        on d.season = c.season
       and d.team = c.team
       and d.position_group = c.position_group
    left join best_returner as b
        on b.season = c.season
       and b.team = c.team
       and b.position_group = c.position_group

)

select
    season,
    team,
    position_group,
    replacement_risk,
    production_returning_pct,
    usage_returning_pct,
    impact_losses,
    impact_additions,
    projected_starters_lost,
    projected_starters_added,
    continuity_score,
    best_returner,
    metric_name,
    departed_metric,
    prior_metric,
    departed_metric / nullif(prior_metric, 0) as departed_share,
    best_returner_metric,
    concat(
        'Highest replacement risk: ', position_group,
        ' — ',
        cast(round(100.0 * coalesce(departed_metric / nullif(prior_metric, 0), 0), 0) as string),
        '% of prior ',
        case metric_name
            when 'pass_att' then 'pass attempts'
            when 'rec_yds' then 'receiving yards'
            when 'rush_yds' then 'rushing yards'
            when 'sacks' then 'sack production'
            when 'tackles' then 'tackle production'
            when 'interceptions' then 'INT production'
            when 'kick_points' then 'kick points'
            else 'production'
        end,
        ' departed',
        case
            when best_returner is not null
            then concat(
                '; best returner ', best_returner,
                ' had ', cast(round(best_returner_metric, 1) as string),
                case metric_name
                    when 'pass_att' then ' attempts'
                    when 'rec_yds' then ' rec yds'
                    when 'rush_yds' then ' rush yds'
                    when 'sacks' then ' sacks'
                    when 'tackles' then ' tackles'
                    when 'interceptions' then ' INTs'
                    when 'kick_points' then ' kick pts'
                    else ' production'
                end
            )
            else ''
        end
    ) as callout
from enriched
where replacement_risk in ('high', 'elevated')
   or continuity_score <= 40
   or coalesce(departed_metric / nullif(prior_metric, 0), 0) >= 0.40
