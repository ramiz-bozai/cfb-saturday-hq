{{ config(alias='departures') }}

/*
    Every way a player leaves a program, in one place: transfer portal moves, NFL draft picks and
    matched undrafted free agents, each carrying the prior-season production earned at the school
    being left.

    portal_moves only covers the portal, so it misses draft and UDFA exits entirely — for Oklahoma
    in 2026 that is most of the departed receiving production. unit_continuity and
    replacement_risk do combine both sources but aggregate to team x position_group, so the player
    names are lost. This model is the player-level view of the same population.

    season is the season the player is gone FOR, matching portal_moves.season and draft_year.
    prior_* columns therefore describe season - 1 at the team being left.

    Dedupe matches gold_replacement_risk: when an athlete appears as both a portal departure and
    an NFL exit in the same season, the portal row wins. Summing prior_* here reconciles with
    replacement_risk.departed_metric once position_group = 'OTHER' is excluded, which is the
    filter that model applies.
*/

with portal_departed as (

    select
        season,
        origin as team,
        athlete_id,
        trim(concat_ws(' ', first_name, last_name)) as player_name,
        {{ position_abbrev('position') }} as position,
        position_group,
        'portal' as departure_type,
        destination,
        cast(null as int) as draft_round,
        cast(null as int) as overall_pick,
        coalesce(prior_usage_overall, 0.0) as prior_usage_overall,
        coalesce(prior_production_score, 0.0) as prior_production_score,
        coalesce(prior_pass_att, 0) as prior_pass_att,
        coalesce(prior_pass_yds, 0) as prior_pass_yds,
        coalesce(prior_rush_yds, 0) as prior_rush_yds,
        coalesce(prior_rec_yds, 0) as prior_rec_yds,
        coalesce(prior_tackles, 0) as prior_tackles,
        coalesce(prior_tfl, 0.0) as prior_tfl,
        coalesce(prior_sacks, 0.0) as prior_sacks,
        coalesce(prior_interceptions, 0) as prior_interceptions,
        coalesce(prior_kick_points, 0) as prior_kick_points
    from {{ ref('gold_portal_moves') }}
    where origin is not null

),

nfl_departed as (

    select
        x.season,
        -- Attribute the exit to where the production was actually earned, falling back to the
        -- draft record's college team. Mirrors gold_replacement_risk so the totals agree.
        coalesce(ps.team, x.college_team) as team,
        x.athlete_id,
        coalesce(
            d.player_name,
            u.display_name,
            trim(concat_ws(' ', u.first_name, u.last_name)),
            ps.player_name
        ) as player_name,
        {{ position_abbrev('coalesce(d.position, u.position, ps.position)') }} as position,
        coalesce(ps.position_group, x.position_group) as position_group,
        x.exit_source as departure_type,
        coalesce(d.nfl_team, u.nfl_team) as destination,
        cast(d.draft_round as int) as draft_round,
        cast(d.overall_pick as int) as overall_pick,
        coalesce(ps.usage_overall, 0.0) as prior_usage_overall,
        coalesce(ps.production_score, 0.0) as prior_production_score,
        coalesce(cast(round(ps.pass_att) as int), 0) as prior_pass_att,
        coalesce(cast(round(ps.pass_yds) as int), 0) as prior_pass_yds,
        coalesce(cast(round(ps.rush_yds) as int), 0) as prior_rush_yds,
        coalesce(cast(round(ps.rec_yds) as int), 0) as prior_rec_yds,
        coalesce(cast(round(ps.tackles) as int), 0) as prior_tackles,
        coalesce(ps.tfl, 0.0) as prior_tfl,
        coalesce(ps.sacks, 0.0) as prior_sacks,
        coalesce(cast(round(ps.interceptions) as int), 0) as prior_interceptions,
        coalesce(cast(round(ps.kick_points) as int), 0) as prior_kick_points
    from {{ nfl_college_exits() }} as x
    left join {{ ref('silver_draft_picks') }} as d
        on x.exit_source = 'draft'
       and d.draft_year = x.season
       and d.athlete_id = x.athlete_id
    left join {{ ref('silver_nfl_udfa') }} as u
        on x.exit_source = 'udfa'
       and u.rookie_year = x.season
       and u.athlete_id = x.athlete_id
    left join {{ ref('gold_player_season') }} as ps
        on ps.athlete_id = x.athlete_id
       and ps.season = x.season - 1
    where not exists (
        select 1
        from portal_departed as p
        where p.season = x.season
          and p.athlete_id = x.athlete_id
    )

)

select * from portal_departed
union all
select * from nfl_departed
