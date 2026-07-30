{{ config(alias='qb_room') }}

/*
    Quarterback room for a preview season with an explicit classification rule tree.

    Enriched from existing gold tables (no new CFBD domains):
      - career pass attempts / career PPA across gold_player_season
      - returning starter = non-transfer who clearly started (>=200 prior att, or
        >=100 and >=50% of team prior pass attempts); never just "top leftover"
      - transfer history from gold_portal_moves
      - backup flag = second-ranked by prior/career attempts
      - turnover rate = INT/att; fumbles_lost when present

    Phase B (deferred — endpoints not landed): success rate, explosiveness,
    sack rate, team W-L with each QB.
*/

with career as (

    select
        athlete_id,
        sum(coalesce(pass_att, 0.0)) as career_pass_att,
        sum(coalesce(pass_yds, 0.0)) as career_pass_yds,
        sum(coalesce(pass_td, 0.0)) as career_pass_td,
        sum(coalesce(pass_int, 0.0)) as career_pass_int,
        sum(coalesce(rush_yds, 0.0)) as career_rush_yds,
        sum(coalesce(rush_att, 0.0)) as career_rush_att,
        sum(coalesce(fumbles_lost, 0.0)) as career_fumbles_lost,
        sum(coalesce(total_ppa_all, 0.0)) as career_total_ppa,
        sum(coalesce(avg_ppa_all, 0.0) * coalesce(pass_att, 0.0))
            / nullif(sum(coalesce(pass_att, 0.0)), 0) as career_avg_ppa_weighted,
        count(distinct season) as seasons_played
    from {{ ref('gold_player_season') }}
    where position_group = 'QB'
       or coalesce(pass_att, 0) > 0
    group by athlete_id

),

transfer_history as (

    select
        player_name_key,
        count(*) as transfer_count,
        max_by(origin, transfer_date) as last_transfer_origin,
        max(transfer_date) as last_transfer_date
    from {{ ref('gold_portal_moves') }}
    group by player_name_key

),

qbs as (

    select
        r.*,
        ps.pass_att as prior_season_pass_att,
        coalesce(r.prior_pass_yds, ps.pass_yds) as pass_yds_prior,
        ps.avg_ppa_all,
        ps.avg_ppa_pass,
        ps.total_ppa_all,
        ps.pass_td,
        ps.pass_int,
        coalesce(r.prior_rush_yds, ps.rush_yds) as qb_rush_yds,
        coalesce(r.prior_rush_att, ps.rush_att) as rush_att_prior,
        coalesce(r.prior_fumbles_lost, ps.fumbles_lost) as fumbles_lost_prior,
        case
            when coalesce(ps.pass_att, 0) > 0
            then coalesce(ps.pass_int, 0) / ps.pass_att
            else null
        end as int_rate,
        case
            when coalesce(ps.pass_att, 0) > 0
            then (coalesce(ps.pass_int, 0) + coalesce(r.prior_fumbles_lost, ps.fumbles_lost, 0)) / ps.pass_att
            else null
        end as turnover_rate,
        c.career_pass_att,
        c.career_pass_yds,
        c.career_pass_td,
        c.career_pass_int,
        c.career_rush_yds,
        c.career_rush_att,
        c.career_fumbles_lost,
        c.career_total_ppa,
        c.career_avg_ppa_weighted,
        c.seasons_played,
        coalesce(th.transfer_count, 0) as transfer_count,
        th.last_transfer_origin,
        th.last_transfer_date,
        coalesce(r.prior_pass_att, ps.pass_att, 0) as attempts_for_rank,
        coalesce(c.career_pass_att, r.prior_pass_att, ps.pass_att, 0) as career_or_prior_att
    from {{ ref('gold_roster_snapshot') }} as r
    left join {{ ref('gold_player_season') }} as ps
        on ps.athlete_id = r.athlete_id
       and ps.season = r.season - 1
    left join career as c
        on c.athlete_id = r.athlete_id
    left join transfer_history as th
        on th.player_name_key = r.player_name_key
    where r.position_group = 'QB'

),

ranked as (

    select
        q.*,
        row_number() over (
            partition by season, team
            order by attempts_for_rank desc, career_or_prior_att desc, coalesce(stars, 0) desc
        ) as qb_rank,
        row_number() over (
            partition by season, team
            order by
                case when not is_transfer_addition then 0 else 1 end,
                attempts_for_rank desc,
                career_or_prior_att desc
        ) as returning_rank
    from qbs as q

),

room_stats as (

    select
        season,
        team,
        count(*) as qb_count,
        max(attempts_for_rank) as max_prior_attempts,
        max(coalesce(avg_ppa_all, 0)) as max_avg_ppa,
        sum(case when is_transfer_addition then 1 else 0 end) as transfer_qbs,
        sum(
            case
                when not is_transfer_addition
                 and coalesce(attempts_for_rank, career_or_prior_att, 0) >= 150
                then 1
                else 0
            end
        ) as proven_returners,
        sum(case when not is_transfer_addition then attempts_for_rank else 0 end) as returning_prior_attempts,
        max(
            case
                when not is_transfer_addition and returning_rank = 1
                then attempts_for_rank
                else 0
            end
        ) as top_returner_attempts
    from ranked
    group by season, team

),

-- Prior-season team pass attempts (denominator for "was this the starter?").
prior_team_passing as (

    select
        season + 1 as season,
        team,
        sum(coalesce(pass_att, 0.0)) as team_prior_pass_att
    from {{ ref('gold_player_season') }}
    where coalesce(pass_att, 0) > 0
    group by season, team

),

classified as (

    select
        q.*,
        r.qb_count,
        r.max_prior_attempts,
        r.max_avg_ppa,
        r.transfer_qbs,
        r.proven_returners,
        -- Only flag a returning starter when we're confident they were THE guy:
        -- non-transfer, top returning passer, and either >=200 prior attempts or
        -- >=50% of the team's prior-season pass attempts (min 100 attempts).
        (
            not q.is_transfer_addition
            and q.returning_rank = 1
            and (
                q.attempts_for_rank >= 200
                or (
                    q.attempts_for_rank >= 100
                    and q.attempts_for_rank >= 0.5 * coalesce(ptp.team_prior_pass_att, 0)
                )
            )
        ) as is_returning_starter,
        q.qb_rank = 2 as is_backup,
        case
            when not q.is_transfer_addition
             and coalesce(q.career_or_prior_att, q.attempts_for_rank, 0) >= 250
             and coalesce(q.career_avg_ppa_weighted, q.avg_ppa_all, 0) >= 0.25
            then 'Proven elite starter'
            when not q.is_transfer_addition
             and coalesce(q.career_or_prior_att, q.attempts_for_rank, 0) >= 150
            then 'Proven average starter'
            when q.is_transfer_addition
             and (
                coalesce(q.career_or_prior_att, q.attempts_for_rank, 0) >= 100
                or coalesce(q.stars, 0) >= 4
             )
            then 'High-upside transfer'
            when not q.is_transfer_addition
             and coalesce(q.career_or_prior_att, q.attempts_for_rank, 0) >= 100
             and coalesce(q.career_avg_ppa_weighted, q.avg_ppa_all, 0) < 0.10
            then 'Experienced but limited'
            when r.proven_returners = 0
             and r.transfer_qbs = 0
             and r.max_prior_attempts < 50
            then 'Major uncertainty'
            when r.qb_count >= 2 and r.proven_returners = 0
            then 'Unproven competition'
            else 'Unproven competition'
        end as qb_class
    from ranked as q
    inner join room_stats as r
        on r.season = q.season
       and r.team = q.team
    left join prior_team_passing as ptp
        on ptp.season = q.season
       and ptp.team = q.team

),

room_class as (

    select
        season,
        team,
        case
            when sum(case when qb_class = 'Major uncertainty' then 1 else 0 end) > 0
             and sum(case when qb_class like 'Proven%' then 1 else 0 end) = 0
            then 'Major uncertainty'
            when sum(case when qb_class = 'Proven elite starter' then 1 else 0 end) > 0
            then 'Proven elite starter'
            when sum(case when qb_class = 'Proven average starter' then 1 else 0 end) > 0
            then 'Proven average starter'
            when sum(case when qb_class = 'High-upside transfer' then 1 else 0 end) > 0
            then 'High-upside transfer'
            when sum(case when qb_class = 'Experienced but limited' then 1 else 0 end) > 0
            then 'Experienced but limited'
            else 'Unproven competition'
        end as room_class,
        max(case when qb_rank = 2 then attempts_for_rank end) as backup_prior_attempts
    from classified
    group by season, team

)

select
    c.season,
    c.team,
    c.athlete_id,
    c.first_name,
    c.last_name,
    c.is_transfer_addition,
    c.is_returning_starter,
    c.is_backup,
    c.qb_rank,
    c.roster_source,
    cast(round(c.prior_pass_att) as int) as prior_pass_att,
    cast(round(c.pass_yds_prior) as int) as prior_pass_yds,
    cast(round(c.career_pass_att) as int) as career_pass_att,
    cast(round(c.career_pass_yds) as int) as career_pass_yds,
    cast(round(c.career_pass_td) as int) as career_pass_td,
    cast(round(c.career_pass_int) as int) as career_pass_int,
    c.career_avg_ppa_weighted,
    c.career_total_ppa,
    c.seasons_played,
    c.avg_ppa_all,
    c.avg_ppa_pass,
    c.total_ppa_all,
    cast(round(c.pass_td) as int) as pass_td,
    cast(round(c.pass_int) as int) as pass_int,
    c.int_rate,
    c.turnover_rate,
    cast(round(c.fumbles_lost_prior) as int) as prior_fumbles_lost,
    cast(round(c.career_fumbles_lost) as int) as career_fumbles_lost,
    cast(round(c.qb_rush_yds) as int) as qb_rush_yds,
    cast(round(c.career_rush_yds) as int) as career_rush_yds,
    cast(round(c.rush_att_prior) as int) as prior_rush_att,
    case
        when coalesce(c.rush_att_prior, 0) + coalesce(c.prior_pass_att, 0) > 0
        then coalesce(c.rush_att_prior, 0)
            / (coalesce(c.rush_att_prior, 0) + coalesce(c.prior_pass_att, 0))
        else null
    end as rush_share_proxy,
    cast(c.stars as int) as stars,
    c.recruiting_rating,
    c.transfer_count,
    c.last_transfer_origin,
    c.last_transfer_date,
    cast(round(rc.backup_prior_attempts) as int) as backup_prior_attempts,
    c.qb_class,
    rc.room_class,
    c.qb_count
from classified as c
inner join room_class as rc
    on rc.season = c.season
   and rc.team = c.team
