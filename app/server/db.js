/**
 * Databricks SQL helper for Saturday HQ app.
 * Local: DATABRICKS_HOST + DATABRICKS_HTTP_PATH + DATABRICKS_TOKEN (or DBT_ACCESS_TOKEN).
 * Apps: DATABRICKS_HOST + DATABRICKS_WAREHOUSE_ID + DATABRICKS_CLIENT_ID/SECRET (OAuth M2M).
 *
 * Reuses one DBSQL client and a small pool of sessions so routes that fire Promise.all
 * do not pay connect/auth on every statement.
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
const SILVER = process.env.SATURDAY_HQ_SILVER_SCHEMA || "cfb_silver";
const APP = process.env.SATURDAY_HQ_APP_SCHEMA || "cfb_app";
const POOL_SIZE = Math.max(1, Number(process.env.DATABRICKS_SQL_POOL_SIZE || 12));

export function gold(table) {
  return `${CATALOG}.${GOLD}.${table}`;
}

export function silver(table) {
  return `${CATALOG}.${SILVER}.${table}`;
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

let client = null;
let clientBoot = null;
const idleSessions = [];
const waiters = [];

async function bootClient() {
  if (client) return client;
  if (clientBoot) return clientBoot;

  clientBoot = (async () => {
    const c = new DBSQLClient({ telemetryEnabled: false });
    await c.connect(connectOptions());
    const sessions = await Promise.all(
      Array.from({ length: POOL_SIZE }, () => c.openSession())
    );
    client = c;
    idleSessions.push(...sessions);
    return c;
  })();

  try {
    return await clientBoot;
  } catch (err) {
    clientBoot = null;
    client = null;
    idleSessions.length = 0;
    waiters.length = 0;
    throw err;
  }
}

async function acquireSession() {
  await bootClient();
  if (idleSessions.length > 0) return idleSessions.pop();
  return new Promise((resolve) => {
    waiters.push(resolve);
  });
}

function releaseSession(session) {
  const waiter = waiters.shift();
  if (waiter) {
    waiter(session);
    return;
  }
  idleSessions.push(session);
}

async function replaceDeadSession() {
  try {
    await bootClient();
    if (!client) return;
    releaseSession(await client.openSession());
  } catch {
    // Pool may shrink until the next successful boot.
  }
}

/**
 * Run SQL on a pooled Databricks session.
 * Safe for concurrent callers (Promise.all) up to DATABRICKS_SQL_POOL_SIZE (default 12).
 */
export async function query(sql) {
  const session = await acquireSession();
  let healthy = true;
  try {
    const op = await session.executeStatement(sql, { runAsync: true, maxRows: 10000 });
    try {
      return await op.fetchAll({ flatten: true });
    } finally {
      await op.close().catch(() => {});
    }
  } catch (err) {
    healthy = false;
    try {
      await session.close();
    } catch {
      // ignore close errors on a dead session
    }
    await replaceDeadSession();
    throw err;
  } finally {
    if (healthy) releaseSession(session);
  }
}

/** Simple process-local TTL cache for expensive JSON responses. */
export function createTtlCache(ttlMs) {
  const map = new Map();
  return {
    get(key) {
      const hit = map.get(key);
      if (!hit) return undefined;
      if (Date.now() > hit.expires) {
        map.delete(key);
        return undefined;
      }
      return hit.value;
    },
    set(key, value) {
      map.set(key, { value, expires: Date.now() + ttlMs });
    },
    clear() {
      map.clear();
    },
  };
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
