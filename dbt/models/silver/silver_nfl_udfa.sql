{{ config(alias='nfl_udfa') }}

/*
    nflverse undrafted free agents.

    rookie_year N = leaves before college season N (same as draft_year).
    athlete_id is resolved via prior-season CFBD roster on player_name_key + college team.
    Multi-school college_name strings ("Oklahoma; California") are exploded; a row is kept
    only when exactly one CFBD athlete_id matches.
*/

with typed as (

    select
        rookie_year,
        gsis_id,
        first_name,
        last_name,
        display_name,
        football_name,
        college,
        college_name,
        nfl_team,
        position,
        {{ position_group('position') }} as position_group,
        draft_number,
        rookie_season,
        {{ player_name_key('first_name', 'last_name') }} as player_name_key,
        {{ player_name_key('football_name', 'last_name') }} as football_name_key,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_nfl_udfa') }}
    where rookie_year is not null
      and gsis_id is not null
      and draft_number is null
      and nullif(trim(first_name), '') is not null
      and nullif(trim(last_name), '') is not null
      and nullif(trim(display_name), '') is not null

),

deduped as (

    select *
    from typed
    qualify row_number() over (
        partition by rookie_year, gsis_id
        order by {{ latest_ingest_first() }}
    ) = 1

),

college_parts as (

    select
        d.*,
        trim(part) as college_part
    from deduped as d
    lateral view explode(
        split(coalesce(nullif(trim(d.college_name), ''), nullif(trim(d.college), ''), ''), ';|/')
    ) e as part
    where trim(part) <> ''

),

normalized as (

    select
        *,
        {{ normalize_nfl_college('college_part') }} as college_team_norm
    from college_parts

),

candidates as (

    select
        n.rookie_year,
        n.gsis_id,
        n.first_name,
        n.last_name,
        n.display_name,
        n.football_name,
        n.college_name,
        n.nfl_team,
        n.position,
        coalesce(r.position_group, n.position_group) as position_group,
        n.player_name_key,
        n._source_path,
        n._ingest_mode,
        r.athlete_id,
        r.team as college_team
    from normalized as n
    inner join {{ ref('silver_rosters') }} as r
        on r.season = n.rookie_year - 1
       and r.team = n.college_team_norm
       and (
           r.player_name_key = n.player_name_key
           or (
               n.football_name is not null
               and r.player_name_key = n.football_name_key
           )
       )
    where n.college_team_norm is not null

),

id_counts as (

    select
        rookie_year,
        gsis_id,
        count(distinct athlete_id) as n_athlete_ids
    from candidates
    group by rookie_year, gsis_id

),

resolved as (

    select
        c.rookie_year,
        c.gsis_id,
        c.first_name,
        c.last_name,
        c.display_name,
        c.football_name,
        c.college_name,
        c.college_team,
        c.nfl_team,
        c.position,
        c.position_group,
        c.player_name_key,
        c.athlete_id,
        c._source_path,
        c._ingest_mode
    from candidates as c
    inner join id_counts as ic
        on ic.rookie_year = c.rookie_year
       and ic.gsis_id = c.gsis_id
       and ic.n_athlete_ids = 1
    qualify row_number() over (
        partition by c.rookie_year, c.gsis_id
        order by c.college_team
    ) = 1

),

unresolved as (

    select
        d.rookie_year,
        d.gsis_id,
        d.first_name,
        d.last_name,
        d.display_name,
        d.football_name,
        d.college_name,
        cast(null as string) as college_team,
        d.nfl_team,
        d.position,
        d.position_group,
        d.player_name_key,
        cast(null as string) as athlete_id,
        d._source_path,
        d._ingest_mode
    from deduped as d
    left join resolved as r
        on r.rookie_year = d.rookie_year
       and r.gsis_id = d.gsis_id
    where r.gsis_id is null

)

select * from resolved
union all
select * from unresolved
