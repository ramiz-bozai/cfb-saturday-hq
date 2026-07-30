{{ config(alias='transfer_dependency') }}

/*
    How dependent a preview-season roster is on transfers.
    Restricted to FBS teams in silver_team_seasons (preview or prior season).
*/

with fbs as (

    select distinct season, team
    from {{ ref('silver_team_seasons') }}

),

roster as (

    select r.*
    from {{ ref('gold_roster_snapshot') }} as r
    where exists (
        select 1
        from fbs
        where fbs.team = r.team
          and fbs.season in (r.season, r.season - 1)
    )

),

team_usage as (

    select
        season,
        team,
        sum(coalesce(prior_usage_overall, 0.0)) as total_prior_usage,
        sum(case when is_transfer_addition then coalesce(prior_usage_overall, 0.0) else 0.0 end) as transfer_usage,
        sum(case when is_transfer_addition and coalesce(prior_usage_overall, 0) >= 0.25 then 1 else 0 end) as transfer_projected_starters,
        avg(case when is_transfer_addition then prior_production_score end) as avg_transfer_prior_production
    from roster
    group by season, team

),

units as (

    select
        season,
        team,
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

)

select
    u.season,
    u.team,
    u.transfer_usage / nullif(u.total_prior_usage, 0) as pct_usage_from_transfers,
    least(
        1.0,
        coalesce(a.added_production, 0) / nullif(d.departed_production, 0)
    ) as pct_departed_production_replaced,
    coalesce(n.critical_units_on_transfers, 0) as critical_units_on_transfers,
    u.avg_transfer_prior_production,
    u.transfer_projected_starters,
    coalesce(n.impact_additions, 0) as impact_additions,
    coalesce(n.impact_losses, 0) as impact_losses,
    -- Composite 0-100 dependency score.
    least(
        100.0,
        greatest(
            0.0,
            100.0 * (
                0.45 * coalesce(u.transfer_usage / nullif(u.total_prior_usage, 0), 0.0)
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
