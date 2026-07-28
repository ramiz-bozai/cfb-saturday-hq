-- Saturday HQ Unity Catalog bootstrap
-- Run in a SQL warehouse / notebook. Equivalent to notebooks/00_setup.py minus the secret
-- check, the volume subfolders, and the demo profile seed rows.
--
-- Two distinct pieces:
--   1. one shared raw catalog holding the CFBD landing volume (created once)
--   2. one catalog per environment for the bronze -> silver -> gold medallion
-- The raw files stay out of both environment catalogs so the CFBD API is only called once.

-- 1. Shared raw landing -------------------------------------------------------------------
CREATE CATALOG IF NOT EXISTS cfb_saturday_hq_raw;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_raw.landing;
CREATE VOLUME IF NOT EXISTS cfb_saturday_hq_raw.landing.cfbd_landing;

-- 2. Per-environment medallion ------------------------------------------------------------
-- Repeat this block for each environment. dbt targets dev by default and prod via
-- `dbt build --target prod`.

-- dev
CREATE CATALOG IF NOT EXISTS cfb_saturday_hq_dev;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_dev.cfb_bronze;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_dev.cfb_silver;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_dev.cfb_gold;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_dev.cfb_ml;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_dev.cfb_app;

-- Model scores. Python fills this during scoring; cfb_gold.matchup_card is a dbt view over
-- it, so it must exist (even empty) before the first dbt run.
CREATE TABLE IF NOT EXISTS cfb_saturday_hq_dev.cfb_gold.game_predictions (
  game_id BIGINT,
  season INT,
  week INT,
  model_home_win_prob DOUBLE,
  model_version STRING,
  scored_at STRING
) USING DELTA;

-- Demo profiles for the App (My Teams)
CREATE TABLE IF NOT EXISTS cfb_saturday_hq_dev.cfb_app.demo_profiles (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA;

CREATE TABLE IF NOT EXISTS cfb_saturday_hq_dev.cfb_app.user_preferences (
  profile_id STRING,
  team STRING,
  updated_at TIMESTAMP
) USING DELTA;

-- prod
CREATE CATALOG IF NOT EXISTS cfb_saturday_hq_prod;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_prod.cfb_bronze;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_prod.cfb_silver;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_prod.cfb_gold;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_prod.cfb_ml;
CREATE SCHEMA IF NOT EXISTS cfb_saturday_hq_prod.cfb_app;

CREATE TABLE IF NOT EXISTS cfb_saturday_hq_prod.cfb_gold.game_predictions (
  game_id BIGINT,
  season INT,
  week INT,
  model_home_win_prob DOUBLE,
  model_version STRING,
  scored_at STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS cfb_saturday_hq_prod.cfb_app.demo_profiles (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA;

CREATE TABLE IF NOT EXISTS cfb_saturday_hq_prod.cfb_app.user_preferences (
  profile_id STRING,
  team STRING,
  updated_at TIMESTAMP
) USING DELTA;
