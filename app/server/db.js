/**
 * Databricks SQL helper for Saturday HQ app.
 * Local: DATABRICKS_HOST + DATABRICKS_HTTP_PATH + DATABRICKS_TOKEN (or DBT_ACCESS_TOKEN).
 * Apps: DATABRICKS_HOST + DATABRICKS_WAREHOUSE_ID + DATABRICKS_CLIENT_ID/SECRET (OAuth M2M).
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { DBSQLClient } from "@databricks/sql";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

loadEnvFile(path.resolve(__dirname, "../../.env"));
loadEnvFile(path.resolve(__dirname, "../.env"));

const CATALOG = process.env.SATURDAY_HQ_CATALOG || "cfb_saturday_hq_prod";
const GOLD = process.env.SATURDAY_HQ_GOLD_SCHEMA || "cfb_gold";
const APP = process.env.SATURDAY_HQ_APP_SCHEMA || "cfb_app";

export function gold(table) {
  return `${CATALOG}.${GOLD}.${table}`;
}

export function appTable(table) {
  return `${CATALOG}.${APP}.${table}`;
}

function host() {
  return (process.env.DATABRICKS_HOST || "")
    .replace(/^https?:\/\//, "")
    .replace(/\/$/, "");
}

function httpPath() {
  if (process.env.DATABRICKS_HTTP_PATH) return process.env.DATABRICKS_HTTP_PATH;
  const wid = process.env.DATABRICKS_WAREHOUSE_ID;
  if (!wid) throw new Error("Set DATABRICKS_WAREHOUSE_ID or DATABRICKS_HTTP_PATH");
  return `/sql/1.0/warehouses/${wid}`;
}

function token() {
  return (
    process.env.DATABRICKS_TOKEN ||
    process.env.DBT_ACCESS_TOKEN ||
    process.env.DATABRICKS_ACCESS_TOKEN ||
    ""
  );
}

function connectOptions() {
  const h = host();
  const p = httpPath();
  if (!h) throw new Error("Set DATABRICKS_HOST");

  const t = token();
  if (t) {
    return { host: h, path: p, token: t };
  }

  const clientId = process.env.DATABRICKS_CLIENT_ID;
  const clientSecret = process.env.DATABRICKS_CLIENT_SECRET;
  if (clientId && clientSecret) {
    return {
      authType: "databricks-oauth",
      host: h,
      path: p,
      oauthClientId: clientId,
      oauthClientSecret: clientSecret,
    };
  }

  return {
    authType: "databricks-oauth",
    host: h,
    path: p,
  };
}

export async function query(sql) {
  const client = new DBSQLClient({ telemetryEnabled: false });
  await client.connect(connectOptions());
  try {
    const session = await client.openSession();
    try {
      const op = await session.executeStatement(sql, { runAsync: true, maxRows: 10000 });
      const rows = await op.fetchAll({ flatten: true });
      await op.close();
      return rows;
    } finally {
      await session.close();
    }
  } finally {
    await client.close();
  }
}

export function esc(value) {
  return String(value ?? "").replace(/'/g, "''");
}

export function seasonStartMonth() {
  return 8;
}

export function defaultSeason(today = new Date()) {
  const y = today.getFullYear();
  const m = today.getMonth() + 1;
  return m >= seasonStartMonth() ? y : y - 1;
}

export function previewSeason(today = new Date()) {
  const y = today.getFullYear();
  const m = today.getMonth() + 1;
  return m < seasonStartMonth() ? y : defaultSeason(today);
}
