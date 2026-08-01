{{ config(alias='draft_picks') }}

/*
    NFL draft picks. draft_year N = athletes who leave before college season N.
*/

with typed as (

    select
        draft_year,
        athlete_id,
        nfl_athlete_id,
        college_id,
        college_team,
        college_conference,
        nfl_team_id,
        nfl_team,
        overall_pick,
        draft_round,
        round_pick,
        player_name,
        position,
        {{ position_group('position') }} as position_group,
        height,
        weight,
        pre_draft_ranking,
        pre_draft_position_ranking,
        pre_draft_grade,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_draft_picks') }}
    where draft_year is not null
      and athlete_id is not null
      and nullif(trim(player_name), '') is not null

)

select *
from typed
qualify row_number() over (
    partition by draft_year, athlete_id
    order by {{ latest_ingest_first() }}
) = 1
