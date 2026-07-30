# Databricks App privileges

The App's service principal needs read-only access to the catalog it serves.

Copy the App service principal's **Application ID** from the App's authorization or permissions
page. Replace `<APP_APPLICATION_ID>` below, retaining the backticks.

## Development catalog

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

## Production catalog

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

The App is read-only, so it does not need `MODIFY`, `CREATE TABLE`, or ownership privileges.
