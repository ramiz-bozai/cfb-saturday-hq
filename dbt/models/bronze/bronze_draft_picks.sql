{{ config(alias='draft_picks') }}

{%- set projection -%}
    cast(year as int) as draft_year,
    cast(collegeAthleteId as string) as athlete_id,
    cast(nflAthleteId as string) as nfl_athlete_id,
    cast(collegeId as string) as college_id,
    collegeTeam as college_team,
    collegeConference as college_conference,
    cast(nflTeamId as string) as nfl_team_id,
    nflTeam as nfl_team,
    cast(overall as int) as overall_pick,
    cast(round as int) as draft_round,
    cast(pick as int) as round_pick,
    name as player_name,
    position,
    cast(height as int) as height,
    cast(weight as int) as weight,
    cast(preDraftRanking as int) as pre_draft_ranking,
    cast(preDraftPositionRanking as int) as pre_draft_position_ranking,
    cast(preDraftGrade as double) as pre_draft_grade
{%- endset -%}

{{ cfbd_union('draft_picks', projection) }}
