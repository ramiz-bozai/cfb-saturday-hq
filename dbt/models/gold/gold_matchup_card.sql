{{ config(alias='matchup_card', materialized='view') }}

/*
    Serving relation for the App, dashboards, and briefs: game features beside the model
    probability and the market's implied probability, both raw and de-vigged.

    A view on purpose. game_predictions is written by Python (ml/train.py score_games), and
    a view means dbt does not have to run again after scoring — the card reflects the newest
    predictions the moment they land. Keeps the pipeline to one handoff each way:
    Python ingest -> dbt -> Python scoring/serving.
*/

select
    f.*,
    p.model_home_win_prob,
    p.model_version,
    p.scored_at,
    -- Against the de-vigged price, not the posted one: the 4.5% overround would otherwise show
    -- up as a standing 2-3 point disagreement in the home team's favour on every game.
    p.model_home_win_prob - f.market_home_win_prob_novig as model_minus_market_home,
    'For analysis and entertainment only. Not gambling advice.' as disclaimer_market
from {{ ref('gold_game_features') }} as f
left join {{ source('cfb_gold', 'game_predictions') }} as p
    on p.game_id = f.game_id
