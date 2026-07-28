{{ config(alias='rankings') }}

-- polls -> ranks is a two-level nesting in the CFBD payload.
with exploded as (

    select
        b.season,
        b.week,
        b.season_type,
        poll_item.poll as poll,
        cast(rank_item.rank as int) as rank,
        rank_item.school as team,
        rank_item.conference as conference_raw,
        {{ normalize_conference('rank_item.conference') }} as conference,
        cast(rank_item.points as double) as points,
        cast(rank_item.firstPlaceVotes as int) as first_place_votes,
        b._source_path,
        b._ingest_mode
    from {{ ref('bronze_rankings') }} as b
    lateral view outer explode(b.polls) polls_exploded as poll_item
    lateral view outer explode(poll_item.ranks) ranks_exploded as rank_item

)

select *
from exploded
qualify row_number() over (
    partition by season, week, poll, team
    order by {{ latest_ingest_first() }}
) = 1
