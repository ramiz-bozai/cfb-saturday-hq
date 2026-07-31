{{ config(alias='portal_team_ledger') }}

/*
    Team-level portal ledger for FBS schools only (preview season membership via
    silver_team_seasons; falls back to prior season if preview year has no row yet).

    Net talent is an average quality delta (avg talent in − avg talent out), not a sum
    of player talent scores — otherwise big portal classes look like “talent losses”
    just from volume.
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

),

counts as (

    select
        season,
        team,
        sum(impact_additions) as impact_additions,
        sum(depth_additions) as depth_additions,
        sum(impact_losses) as impact_losses,
        sum(depth_losses) as depth_losses,
        sum(net_production_gained) as net_production_gained,
        sum(projected_starters_added) as projected_starters_added,
        sum(projected_starters_lost) as projected_starters_lost,
        avg(continuity_score) as avg_continuity_score
    from continuity
    group by season, team

),

talent_moves as (

    select
        season,
        team,
        side,
        talent_score
    from (
        select
            season,
            destination as team,
            'in' as side,
            talent_score
        from {{ ref('gold_portal_moves') }}
        where destination is not null

        union all

        select
            season,
            origin as team,
            'out' as side,
            talent_score
        from {{ ref('gold_portal_moves') }}
        where origin is not null
          and (destination is null or destination <> origin)

        union all

        select
            x.season,
            coalesce(ps.team, x.college_team) as team,
            'out' as side,
            ps.talent_score as talent_score
        from {{ nfl_college_exits() }} as x
        left join {{ ref('gold_player_season') }} as ps
            on ps.athlete_id = x.athlete_id
           and ps.season = x.season - 1
        where x.athlete_id is not null
          and coalesce(ps.position_group, x.position_group) not in ('OTHER')
          and not exists (
              select 1
              from {{ ref('gold_portal_moves') }} as m
              where m.season = x.season
                and m.athlete_id = x.athlete_id
                and m.origin is not null
          )
    )
    where team is not null

),

team_talent as (

    select
        season,
        team,
        avg(case when side = 'in' then talent_score end) as talent_added,
        avg(case when side = 'out' then talent_score end) as talent_lost
    from talent_moves
    group by season, team

)

select
    c.season,
    c.team,
    c.impact_additions,
    c.depth_additions,
    c.impact_losses,
    c.depth_losses,
    c.net_production_gained,
    case
        when t.talent_added is null and t.talent_lost is null then null
        else coalesce(t.talent_added, 0.0) - coalesce(t.talent_lost, 0.0)
    end as net_talent_gained,
    t.talent_added,
    t.talent_lost,
    c.projected_starters_added,
    c.projected_starters_lost,
    c.avg_continuity_score
from counts as c
left join team_talent as t
    on t.season = c.season
   and t.team = c.team
