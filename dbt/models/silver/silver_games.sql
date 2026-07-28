{{ config(alias='games') }}

with typed as (

    select
        game_id,
        season,
        week,
        season_type,
        start_date,
        completed,
        neutral_site,
        conference_game,
        home_id,
        home_team,
        home_conference as home_conference_raw,
        {{ normalize_conference('home_conference') }} as home_conference,
        home_classification,
        home_points,
        away_id,
        away_team,
        away_conference as away_conference_raw,
        {{ normalize_conference('away_conference') }} as away_conference,
        away_classification,
        away_points,
        venue_id,
        venue,
        lower(coalesce(home_classification, '')) = 'fbs'
            or lower(coalesce(away_classification, '')) = 'fbs' as is_fbs_game,
        case
            when completed and home_points is not null and away_points is not null
                then home_points > away_points
        end as home_won,
        case when completed then home_points - away_points end as margin_home,
        case when completed then home_points + away_points end as total_points,
        _source_path,
        _ingest_mode
    from {{ ref('bronze_games') }}

),

deduped as (

    select *
    from typed
    qualify row_number() over (
        partition by game_id
        order by {{ latest_ingest_first() }}
    ) = 1

)

-- Keep games involving at least one FBS team (SOS / schedule completeness)
select *
from deduped
where is_fbs_game
