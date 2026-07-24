-- Saturday HQ Unity Catalog bootstrap
-- Run in a SQL warehouse / notebook after replacing ${catalog} if needed.

CREATE CATALOG IF NOT EXISTS cfb_saturday_hq;
USE CATALOG cfb_saturday_hq;

CREATE SCHEMA IF NOT EXISTS cfb_bronze;
CREATE SCHEMA IF NOT EXISTS cfb_silver;
CREATE SCHEMA IF NOT EXISTS cfb_gold;
CREATE SCHEMA IF NOT EXISTS cfb_ml;
CREATE SCHEMA IF NOT EXISTS cfb_app;

-- Landing volume for historical JSONL downloads and daily incremental drops
CREATE VOLUME IF NOT EXISTS bronze.cfbd_landing;

-- Demo profiles for the App (My Teams)
CREATE TABLE IF NOT EXISTS app.demo_profiles (
  profile_id STRING,
  display_name STRING,
  teams ARRAY<STRING>
) USING DELTA;

CREATE TABLE IF NOT EXISTS app.user_preferences (
  profile_id STRING,
  team STRING,
  updated_at TIMESTAMP
) USING DELTA;
