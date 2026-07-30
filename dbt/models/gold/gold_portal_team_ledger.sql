{{ config(alias='portal_team_ledger') }}

/*
    Team-level portal ledger for FBS schools only (preview season membership via
    silver_team_seasons; falls back to prior season if preview year has no row yet).
*/

with fbs as (

    select distinct
        season,
        team
    from {{ ref('silver_team_seasons') }}

),

continuity as (

    select
        uc.*
    from {{ ref('gold_unit_continuity') }} as uc
    where exists (
        select 1
        from fbs
        where fbs.team = uc.team
          and fbs.season in (uc.season, uc.season - 1)
    )

)

select
    season,
    team,
    sum(impact_additions) as impact_additions,
    sum(depth_additions) as depth_additions,
    sum(impact_losses) as impact_losses,
    sum(depth_losses) as depth_losses,
    sum(net_production_gained) as net_production_gained,
    sum(net_talent_gained) as net_talent_gained,
    sum(talent_added) as talent_added,
    sum(talent_lost) as talent_lost,
    sum(projected_starters_added) as projected_starters_added,
    sum(projected_starters_lost) as projected_starters_lost,
    avg(continuity_score) as avg_continuity_score
from continuity
group by season, team
