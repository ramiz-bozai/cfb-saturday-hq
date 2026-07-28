-- Saturday HQ Unity Catalog bootstrap
-- Run in a SQL warehouse / notebook

CREATE CATALOG IF NOT EXISTS cfb_saturday_hq;
USE CATALOG cfb_saturday_hq;

CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq.cfb_bronze;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq.cfb_silver;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq.cfb_gold;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq.cfb_ml;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq.cfb_app;

-- Landing volume for historical JSONL downloads and daily incremental drops
CREATE VOLUME IF NOT EXISTS cfb_bronze.cfbd_landing;

-- Model scores. Python fills this during scoring; cfb_gold.matchup_card is a dbt view over
-- it, so it must exist (even empty) before the first dbt run.
CREATE TABLE IF NOT EXISTS cfb_gold.game_predictions (
  game_id BIGINT,
  season INT,
  week INT,
  model_home_win_prob DOUBLE,
  model_version STRING,
  scored_at STRING
) USING DELTA;

-- Demo profiles for the App (My Teams)
CREATE TABLE IF NOT EXISTS cfb_app.demo_profiles (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA;

CREATE TABLE IF NOT EXISTS cfb_app.user_preferences (
  profile_id STRING,
  team STRING,
  updated_at TIMESTAMP
) USING DELTA;
