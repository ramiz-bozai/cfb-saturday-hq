{{ config(alias='transfer_dependency') }}

/*
    How dependent a preview-season roster is on transfers.
    Restricted to FBS teams in silver_team_seasons (preview or prior season).

    Scores:
      transfer_dependency_score — all position groups
      offense_transfer_dependency_score — QB, RB, WR/TE, OL
      defense_transfer_dependency_score — DL, LB, DB
*/

with fbs as (

    select distinct season, team
    from {{ ref('silver_team_seasons') }}

),

roster as (

    select
        r.*,
        case
            when r.position_group in ('QB', 'RB', 'WR/TE', 'OL') then 'offense'
            when r.position_group in ('DL', 'LB', 'DB') then 'defense'
            else 'special'
        end as side
    from {{ ref('gold_roster_snapshot') }} as r
    where exists (
        select 1
        from fbs
        where fbs.team = r.team
          and fbs.season in (r.season, r.season - 1)
    )

),

usage_by_side as (

    select
        season,
        team,
        side,
        sum(coalesce(prior_usage_overall, 0.0)) as total_prior_usage,
        sum(case when is_transfer_addition then coalesce(prior_usage_overall, 0.0) else 0.0 end) as transfer_usage,
        sum(coalesce(prior_production_score, 0.0)) as total_prior_production,
        sum(case when is_transfer_addition then coalesce(prior_production_score, 0.0) else 0.0 end) as transfer_production,
        sum(
            case
                when is_transfer_addition
                 and (
                     coalesce(prior_usage_overall, 0) >= 0.25
                     or coalesce(prior_production_score, 0) >= 40.0
                 )
                then 1
                else 0
            end
        ) as transfer_projected_starters,
        avg(case when is_transfer_addition then prior_production_score end) as avg_transfer_prior_production
    from roster
    group by season, team, side

),

team_usage as (

    select
        season,
        team,
        sum(coalesce(prior_usage_overall, 0.0)) as total_prior_usage,
        sum(case when is_transfer_addition then coalesce(prior_usage_overall, 0.0) else 0.0 end) as transfer_usage,
        sum(coalesce(prior_production_score, 0.0)) as total_prior_production,
        sum(case when is_transfer_addition then coalesce(prior_production_score, 0.0) else 0.0 end) as transfer_production,
        sum(
            case
                when is_transfer_addition
                 and (
                     coalesce(prior_usage_overall, 0) >= 0.25
                     or coalesce(prior_production_score, 0) >= 40.0
                 )
                then 1
                else 0
            end
        ) as transfer_projected_starters,
        avg(case when is_transfer_addition then prior_production_score end) as avg_transfer_prior_production
    from roster
    group by season, team

),

units_by_side as (

    select
        season,
        team,
        case
            when position_group in ('QB', 'RB', 'WR/TE', 'OL') then 'offense'
            when position_group in ('DL', 'LB', 'DB') then 'defense'
            else 'special'
        end as side,
        count(case when replacement_risk in ('high', 'elevated') and impact_additions > 0 then 1 end) as critical_units_on_transfers,
        sum(impact_additions) as impact_additions,
        sum(impact_losses) as impact_losses
    from {{ ref('gold_unit_continuity') }} as uc
    where exists (
        select 1
        from fbs
        where fbs.team = uc.team
          and fbs.season in (uc.season, uc.season - 1)
    )
    group by season, team, 3

),

units as (

    select
        season,
        team,
        sum(critical_units_on_transfers) as critical_units_on_transfers,
        sum(impact_additions) as impact_additions,
        sum(impact_losses) as impact_losses
    from units_by_side
    group by season, team

),

departed as (

    select
        season,
        origin as team,
        sum(prior_production_score) as departed_production
    from {{ ref('gold_portal_moves') }}
    where origin is not null
      and (destination is null or destination <> origin)
    group by season, origin

),

added as (

    select
        season,
        destination as team,
        sum(prior_production_score) as added_production
    from {{ ref('gold_portal_moves') }}
    where destination is not null
    group by season, destination

),

score as (

    select
        u.season,
        u.team,
        u.side,
        coalesce(
            u.transfer_usage / nullif(u.total_prior_usage, 0),
            u.transfer_production / nullif(u.total_prior_production, 0)
        ) as pct_usage_from_transfers,
        coalesce(n.critical_units_on_transfers, 0) as critical_units_on_transfers,
        u.avg_transfer_prior_production,
        u.transfer_projected_starters,
        least(
            100.0,
            greatest(
                0.0,
                100.0 * (
                    0.45 * coalesce(
                        u.transfer_usage / nullif(u.total_prior_usage, 0),
                        u.transfer_production / nullif(u.total_prior_production, 0),
                        0.0
                    )
                    + 0.25 * least(1.0, coalesce(n.critical_units_on_transfers, 0) / 4.0)
                    + 0.20 * least(1.0, coalesce(u.transfer_projected_starters, 0) / 5.0)
                    + 0.10 * least(1.0, coalesce(u.avg_transfer_prior_production, 0) / 40.0)
                )
            )
        ) as transfer_dependency_score
    from usage_by_side as u
    left join units_by_side as n
        on n.season = u.season
       and n.team = u.team
       and n.side = u.side

),

overall as (

    select
        u.season,
        u.team,
        coalesce(
            u.transfer_usage / nullif(u.total_prior_usage, 0),
            u.transfer_production / nullif(u.total_prior_production, 0)
        ) as pct_usage_from_transfers,
        least(
            1.0,
            coalesce(a.added_production, 0) / nullif(d.departed_production, 0)
        ) as pct_departed_production_replaced,
        coalesce(n.critical_units_on_transfers, 0) as critical_units_on_transfers,
        u.avg_transfer_prior_production,
        u.transfer_projected_starters,
        coalesce(n.impact_additions, 0) as impact_additions,
        coalesce(n.impact_losses, 0) as impact_losses,
        least(
            100.0,
            greatest(
                0.0,
                100.0 * (
                    0.45 * coalesce(
                        u.transfer_usage / nullif(u.total_prior_usage, 0),
                        u.transfer_production / nullif(u.total_prior_production, 0),
                        0.0
                    )
                    + 0.25 * least(1.0, coalesce(n.critical_units_on_transfers, 0) / 4.0)
                    + 0.20 * least(1.0, coalesce(u.transfer_projected_starters, 0) / 5.0)
                    + 0.10 * least(1.0, coalesce(u.avg_transfer_prior_production, 0) / 40.0)
                )
            )
        ) as transfer_dependency_score
    from team_usage as u
    left join units as n
        on n.season = u.season and n.team = u.team
    left join departed as d
        on d.season = u.season and d.team = u.team
    left join added as a
        on a.season = u.season and a.team = u.team

)

select
    o.season,
    o.team,
    o.pct_usage_from_transfers,
    o.pct_departed_production_replaced,
    o.critical_units_on_transfers,
    o.avg_transfer_prior_production,
    o.transfer_projected_starters,
    o.impact_additions,
    o.impact_losses,
    o.transfer_dependency_score,
    off.pct_usage_from_transfers as offense_pct_usage_from_transfers,
    off.critical_units_on_transfers as offense_critical_units_on_transfers,
    off.transfer_dependency_score as offense_transfer_dependency_score,
    def.pct_usage_from_transfers as defense_pct_usage_from_transfers,
    def.critical_units_on_transfers as defense_critical_units_on_transfers,
    def.transfer_dependency_score as defense_transfer_dependency_score
from overall as o
left join score as off
    on off.season = o.season
   and off.team = o.team
   and off.side = 'offense'
left join score as def
    on def.season = o.season
   and def.team = o.team
   and def.side = 'defense'
