{{ config(alias='hs_recruiting_class') }}

/*
    Incoming high-school recruiting class by signing school.

    Grain: class_year × team (committed_to).
    Team score = average CFBD rating among rated signees only (no stars/5 fill).
    class_rank is national rank among teams with >= 10 rated signees; null otherwise.
*/

with classes as (

    select
        class_year as season,
        committed_to as team,
        count(*) as signees,
        count_if(rating is not null) as rated_signees,
        round(avg(stars), 2) as avg_stars,
        count_if(stars >= 4) as four_stars,
        count_if(stars >= 5) as five_stars,
        round(avg(rating), 3) as avg_rating
    from {{ ref('silver_recruiting_players') }}
    where class_year is not null
      and committed_to is not null
    group by class_year, committed_to

),

ranked as (

    select
        season,
        team,
        rank() over (
            partition by season
            order by avg_rating desc
        ) as class_rank
    from classes
    where rated_signees >= 10
      and avg_rating is not null

)

select
    c.season,
    c.team,
    c.signees,
    c.rated_signees,
    c.avg_stars,
    c.four_stars,
    c.five_stars,
    c.avg_rating,
    r.class_rank
from classes as c
left join ranked as r
    on r.season = c.season
   and r.team = c.team
