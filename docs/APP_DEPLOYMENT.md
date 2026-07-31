# Databricks App

Saturday HQ is a **Node.js Databricks App**: React (Vite) SPA + Express API that queries
`cfb_gold` / `cfb_app` through a SQL warehouse.

## Runtime

- Entry: `app/app.yaml` → `npm run start` (builds the client via `prestart`, then serves
  Express on `DATABRICKS_APP_PORT`)
- Local: from `app/`, `npm run dev` (Vite on `:5173` proxied to Express on `:8000`)
- Auth: PAT locally (`DATABRICKS_TOKEN` / `DBT_ACCESS_TOKEN`); Apps use OAuth M2M
  (`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`) plus `DATABRICKS_WAREHOUSE_ID`

## Privileges

The App's service principal needs read-only access to the catalog it serves.

Copy the App service principal's **Application ID** from the App's authorization or permissions
page. Replace `<APP_APPLICATION_ID>` below, retaining the backticks.

### Development catalog

```sql
GRANT USE CATALOG
ON CATALOG cfb_saturday_hq_dev
TO `<APP_APPLICATION_ID>`;

GRANT USE SCHEMA
ON SCHEMA cfb_saturday_hq_dev.cfb_gold
TO `<APP_APPLICATION_ID>`;

GRANT SELECT
ON SCHEMA cfb_saturday_hq_dev.cfb_gold
TO `<APP_APPLICATION_ID>`;

GRANT USE SCHEMA
ON SCHEMA cfb_saturday_hq_dev.cfb_app
TO `<APP_APPLICATION_ID>`;

GRANT SELECT
ON SCHEMA cfb_saturday_hq_dev.cfb_app
TO `<APP_APPLICATION_ID>`;
```

### Production catalog

Run the equivalent grants before pointing `app/app.yaml` at production:

```sql
GRANT USE CATALOG
ON CATALOG cfb_saturday_hq_prod
TO `<APP_APPLICATION_ID>`;

GRANT USE SCHEMA
ON SCHEMA cfb_saturday_hq_prod.cfb_gold
TO `<APP_APPLICATION_ID>`;

GRANT SELECT
ON SCHEMA cfb_saturday_hq_prod.cfb_gold
TO `<APP_APPLICATION_ID>`;

GRANT USE SCHEMA
ON SCHEMA cfb_saturday_hq_prod.cfb_app
TO `<APP_APPLICATION_ID>`;

GRANT SELECT
ON SCHEMA cfb_saturday_hq_prod.cfb_app
TO `<APP_APPLICATION_ID>`;
```

The App is read-only for serving briefs/chat. Filling briefs with
`app/scripts/warm_genie_briefs.js` needs a user or service principal with **MODIFY** on
`cfb_app.genie_team_briefs` plus Genie Can Run on the space.
