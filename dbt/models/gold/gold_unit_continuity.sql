{{ config(alias='unit_continuity') }}

/*
    Continuity grades by team × position group for a Season Preview target season.

    Talent fields:
      recruiting_talent_returning — avg talent_score of non-transfer roster players
      talent_added / talent_lost — avg talent_score of portal (and draft) gains/losses
      net_talent_gained — average talent delta: avg(in) − avg(out), not a headcount sum
*/

with roster as (

    select *
    from {{ ref('gold_roster_snapshot') }}
    where position_group not in ('OTHER')

),

-- Position group from prior-season roster (authoritative); production/usage from player_season.
-- Usage/PPA-only grains miss OL/DL/LB/DB/ST, which left production/usage returning null in the UI.
prior_group as (

    select
        rost.season,
        rost.team,
        rost.position_group,
        sum(coalesce(ps.production_score, 0.0)) as production_score,
        sum(coalesce(ps.usage_overall, 0.0)) as usage_overall,
        avg(ps.stars) as avg_stars,
        sum(coalesce(ps.talent_score, 0.0)) as talent_score,
        count(*) as prior_roster_players
    from {{ ref('silver_rosters') }} as rost
    left join {{ ref('gold_player_season') }} as ps
        on ps.season = rost.season
       and ps.athlete_id = rost.athlete_id
       and ps.team = rost.team
    where rost.position_group not in ('OTHER')
    group by rost.season, rost.team, rost.position_group

),

returning as (

    select
        season,
        team,
        position_group,
        sum(case when not is_transfer_addition then coalesce(prior_production_score, 0.0) else 0.0 end) as returning_production,
        sum(case when not is_transfer_addition then coalesce(prior_usage_overall, 0.0) else 0.0 end) as returning_usage,
        avg(case when not is_transfer_addition then stars end) as returning_avg_stars,
        avg(case when not is_transfer_addition then coalesce(prior_talent_score, cast(stars as double) / 5.0) end) as returning_avg_talent,
        sum(case when not is_transfer_addition then coalesce(prior_talent_score, cast(stars as double) / 5.0, 0.0) else 0.0 end) as talent_returning,
        count(case when not is_transfer_addition then 1 end) as returning_players,
        count(case when is_transfer_addition then 1 end) as transfer_additions,
        sum(case when is_transfer_addition then coalesce(prior_production_score, 0.0) else 0.0 end) as transfer_added_production,
        avg(case when not is_transfer_addition then class_year end) as avg_class_year
    from roster
    group by season, team, position_group

),

portal_losses as (

    select
        season,
        team,
        position_group,
        count(*) as transfer_departures,
        sum(case when impact_class = 'impact' then 1 else 0 end) as impact_losses,
        sum(case when impact_class = 'depth' then 1 else 0 end) as depth_losses,
        sum(prior_production_score) as departed_production,
        sum(case when projected_starter then 1 else 0 end) as projected_starters_lost,
        avg(talent_score) as talent_lost
    from (
        select
            season,
            origin as team,
            position_group,
            impact_class,
            prior_production_score,
            projected_starter,
            talent_score
        from {{ ref('gold_portal_moves') }}
        where origin is not null
          and (destination is null or destination <> origin)

        union all

        -- NFL exits (draft + matched UDFA) not already in portal still leave production holes.
        select
            x.season,
            coalesce(ps.team, x.college_team) as team,
            coalesce(ps.position_group, x.position_group) as position_group,
            {{ preview_impact_class(
                "coalesce(ps.position_group, x.position_group)",
                'ps.usage_overall',
                'ps.production_score',
                'ps.talent_score',
                'ps.stars',
                'ps.athlete_id is not null'
            ) }} as impact_class,
            coalesce(ps.production_score, 0.0) as prior_production_score,
            {{ preview_projected_starter(
                "coalesce(ps.position_group, x.position_group)",
                'ps.usage_overall',
                'ps.production_score',
                'ps.talent_score',
                'ps.stars',
                'ps.athlete_id is not null'
            ) }} as projected_starter,
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
    group by season, team, position_group

),

portal_gains as (

    select
        season,
        destination as team,
        position_group,
        sum(case when impact_class = 'impact' then 1 else 0 end) as impact_additions,
        sum(case when impact_class = 'depth' then 1 else 0 end) as depth_additions,
        sum(prior_production_score) as added_production,
        sum(case when projected_starter then 1 else 0 end) as projected_starters_added,
        avg(transfer_stars) as avg_transfer_stars,
        avg(talent_score) as talent_added
    from {{ ref('gold_portal_moves') }}
    where destination is not null
    group by season, destination, position_group

)

select
    r.season,
    r.team,
    r.position_group,
    r.returning_players,
    -- OL/ST have no CFBD usage/PPA — leave retained null (UI shows —). Else production or headcount.
    case
        when r.position_group in ('OL', 'ST') then null
        else least(
            1.0,
            greatest(
                0.0,
                case
                    when coalesce(pg.production_score, 0) > 1
                    then r.returning_production / nullif(pg.production_score, 0)
                    else coalesce(
                        coalesce(r.returning_players, 0)
                            / nullif(coalesce(r.returning_players, 0) + coalesce(pl.transfer_departures, 0), 0),
                        0.0
                    )
                end
            )
        )
    end as production_returning_pct,
    case
        when r.position_group in ('OL', 'ST') then null
        else least(
            1.0,
            greatest(
                0.0,
                case
                    when coalesce(pg.usage_overall, 0) > 0.05
                    then r.returning_usage / nullif(pg.usage_overall, 0)
                    when coalesce(pg.production_score, 0) > 1
                    then r.returning_production / nullif(pg.production_score, 0)
                    else coalesce(
                        coalesce(r.returning_players, 0)
                            / nullif(coalesce(r.returning_players, 0) + coalesce(pl.transfer_departures, 0), 0),
                        0.0
                    )
                end
            )
        )
    end as usage_returning_pct,
    r.returning_avg_stars,
    r.avg_class_year as experience,
    coalesce(pl.transfer_departures, 0) as transfer_departures,
    coalesce(pgain.impact_additions, 0) + coalesce(pgain.depth_additions, 0) as transfer_additions,
    coalesce(pgain.impact_additions, 0) as impact_additions,
    coalesce(pgain.depth_additions, 0) as depth_additions,
    coalesce(pl.impact_losses, 0) as impact_losses,
    coalesce(pl.depth_losses, 0) as depth_losses,
    coalesce(pgain.added_production, 0) - coalesce(pl.departed_production, 0) as net_production_gained,
    coalesce(r.talent_returning, 0.0) as talent_returning,
    pgain.talent_added as talent_added,
    pl.talent_lost as talent_lost,
    -- Average talent quality in minus average talent quality out (0–1 scale).
    case
        when pgain.talent_added is null and pl.talent_lost is null then null
        else coalesce(pgain.talent_added, 0.0) - coalesce(pl.talent_lost, 0.0)
    end as net_talent_gained,
    coalesce(r.returning_avg_talent, 0.0) as recruiting_talent_returning,
    pgain.talent_added as recruiting_talent_added,
    pl.talent_lost as recruiting_talent_lost,
    coalesce(pgain.avg_transfer_stars, 0) - coalesce(r.returning_avg_stars, 0) as net_talent_proxy,
    coalesce(pgain.projected_starters_added, 0) as projected_starters_added,
    coalesce(pl.projected_starters_lost, 0) as projected_starters_lost,
    -- Continuity score 0-100. Prefer usage+production when both exist; production alone
    -- for DL/LB/DB (no CFBD usage); else returning headcount share (OL/ST).
    least(
        100.0,
        greatest(
            0.0,
            case
                when coalesce(pg.usage_overall, 0) > 0.05
                 and coalesce(pg.production_score, 0) > 1
                then 100.0 * (
                    0.6 * coalesce(r.returning_usage / nullif(pg.usage_overall, 0), 0.0)
                    + 0.4 * coalesce(r.returning_production / nullif(pg.production_score, 0), 0.0)
                )
                when coalesce(pg.usage_overall, 0) > 0.05
                then 100.0 * coalesce(r.returning_usage / nullif(pg.usage_overall, 0), 0.0)
                when coalesce(pg.production_score, 0) > 1
                then 100.0 * coalesce(r.returning_production / nullif(pg.production_score, 0), 0.0)
                else 100.0 * (
                    coalesce(r.returning_players, 0)
                    / nullif(coalesce(r.returning_players, 0) + coalesce(pl.transfer_departures, 0), 0)
                )
            end
        )
    ) as continuity_score,
    case
        when coalesce(pl.departed_production, 0) > 0
         and coalesce(r.returning_production, 0) < 0.3 * coalesce(pl.departed_production, 0)
        then 'high'
        when coalesce(pl.impact_losses, 0) >= 1
         and coalesce(pgain.impact_additions, 0) = 0
        then 'elevated'
        else 'manageable'
    end as replacement_risk
from returning as r
left join prior_group as pg
    on pg.season = r.season - 1
   and pg.team = r.team
   and pg.position_group = r.position_group
left join portal_losses as pl
    on pl.season = r.season
   and pl.team = r.team
   and pl.position_group = r.position_group
left join portal_gains as pgain
    on pgain.season = r.season
   and pgain.team = r.team
   and pgain.position_group = r.position_group
