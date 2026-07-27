{{ config(alias='matchup_card') }}

/*
    Serving table for the App, dashboards, and briefs: game features beside the model
    probability and the market's implied probability.

    game_predictions is written by src/saturday_hq/ml/train.py, so this model runs in a
    second dbt pass after scoring:

        dbt build --exclude gold_matchup_card   # before scoring
        <run the training/scoring notebook>
        dbt build --select gold_matchup_card    # after scoring
*/

select
    f.*,
    p.model_home_win_prob,
    p.model_version,
    p.scored_at,
    p.model_home_win_prob - f.market_home_win_prob_implied as model_minus_market_home,
    'For analysis and entertainment only. Not gambling advice.' as disclaimer_market
from {{ ref('gold_game_features') }} as f
left join {{ source('cfb_gold', 'game_predictions') }} as p
    on p.game_id = f.game_id
