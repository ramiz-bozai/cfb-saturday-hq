{{ config(
    alias='genie_team_briefs',
    materialized='incremental',
    unique_key=['season', 'team'],
    incremental_strategy='append',
    tags=['app', 'genie']
) }}

/*
    Skeleton rows for Season Preview Genie briefs (cfb_app.genie_team_briefs).

    dbt only inserts (season, team, prompt) for teams not already present.
    brief_text / conversation ids are filled by app/scripts/warm_genie_briefs.js
    via the Genie Conversation API — never overwritten here on rebuild.
*/

with teams as (

    select distinct
        season,
        team
    from {{ ref('gold_returning_production_team') }}
    where conference is not null
      and team is not null
      and season = (
          select max(season)
          from {{ ref('gold_returning_production_team') }}
          where conference is not null
      )

)

select
    t.season,
    t.team,
    concat(
        'What''s the bottom line and outlook for ',
        t.team,
        ' ',
        cast(t.season as string),
        ' season? In 3-4 sentences max. Do not be very heavy on just regurgitating statistics.'
    ) as prompt,
    cast(null as string) as brief_text,
    cast(null as string) as conversation_id,
    cast(null as string) as message_id,
    cast(null as string) as space_id,
    cast(null as timestamp) as generated_at
from teams as t
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} as existing
    where existing.season = t.season
      and existing.team = t.team
)
{% endif %}
