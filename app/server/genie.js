/**
 * Databricks Genie Conversation API client for Saturday HQ.
 */
import {
  appTable,
  createTtlCache,
  esc,
  gold,
  query,
  previewSeason,
} from "./db.js";
import { getScheduleCompetitionNote } from "./scheduleDifficulty.js";

export { getScheduleCompetitionNote, getScheduleDifficulty } from "./scheduleDifficulty.js";

const SPACE_ID =
  process.env.GENIE_SPACE_ID || "01f18c7f92fa18cbbdb18f2248cbec37";

/**
 * Briefs use natural language (no table-name forcing). Vague "outlook" alone
 * still tends to hit metric views; asking for portal + QB steers Genie to
 * portal_moves / qb_room.
 *
 * Returning QBs are easy to miss when Genie over-indexes on portal_moves
 * (e.g. Texas / Arch Manning), but forcing QB into every sentence makes briefs
 * robotic and QB-heavy. Inject returning-QB names as soft optional context.
 * Schedule/competition is injected only when upcoming games exist in silver.
 */
const BRIEF_FACTS_PROMPT = (team, season, qbNote = null) => {
  const qbBit = qbNote
    ? ` (FYI returning QB includes ${qbNote} — include only if they're part of the real story, not as the whole story.)`
    : "";
  return `For ${team} in ${season}, what are the biggest portal additions and losses, and how does the QB situation fit in? Lead with the roster moves that matter most; QB is one thread, not the whole brief.${qbBit} Do not ask clarifying questions.`;
};

const BRIEF_NARRATIVE_PROMPT = (
  team,
  season,
  { scheduleNote = null, qbNote = null } = {}
) => {
  const qbBit = qbNote
    ? ` You may weave in ${qbNote} if the QB situation matters, but don't make the whole outlook about the QB room.`
    : "";
  const scheduleBit = scheduleNote
    ? ` If it fits, briefly touch schedule competition using: ${scheduleNote}`
    : "";
  return `Using that, write a polished conversational bottom-line outlook for ${team}'s ${season} season in at most 4 sentences. Balance the team's biggest storylines — portal impact, key losses, and QB only where it actually moves the needle. Freestyle the order and tone; don't sound like a checklist. Do not lead with percentages or continuity scores. Do not ask clarifying questions.${qbBit}${scheduleBit}`;
};

/** Single-shot fallback when two-step fails or clarifies. */
const BRIEF_SINGLE_PROMPT = (
  team,
  season,
  { scheduleNote = null, qbNote = null } = {}
) => {
  const qbBit = qbNote
    ? ` QB context if useful: ${qbNote} is a returning starter — mention only if it belongs in the story.`
    : "";
  const scheduleBit = scheduleNote
    ? ` If it fits, briefly note schedule competition using: ${scheduleNote}`
    : "";
  return `For ${team} in ${season}, write a polished conversational season outlook in at most 4 sentences. Weight the biggest portal adds/losses; treat QB as one thread among others.${qbBit} Freestyle — not a stats dump or checklist. Do not ask clarifying questions.${scheduleBit}`;
};

/** Strip Genie markdown (bold/italic/code) so UI shows plain prose. */
export function cleanGenieText(text) {
  if (text == null) return null;
  return String(text)
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1")
    .replace(/_([^_\n]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

const briefMemCache = createTtlCache(5 * 60 * 1000);

function workspaceHost() {
  return (process.env.DATABRICKS_HOST || "")
    .replace(/^https?:\/\//, "")
    .replace(/\/$/, "");
}

function staticToken() {
  return (
    process.env.DATABRICKS_TOKEN ||
    process.env.DBT_ACCESS_TOKEN ||
    process.env.DATABRICKS_ACCESS_TOKEN ||
    ""
  );
}

let cachedOauth = null;

async function workspaceToken() {
  const t = staticToken();
  if (t) return t;

  if (cachedOauth && Date.now() < cachedOauth.expires) return cachedOauth.token;

  const clientId = process.env.DATABRICKS_CLIENT_ID;
  const clientSecret = process.env.DATABRICKS_CLIENT_SECRET;
  const host = workspaceHost();
  if (!clientId || !clientSecret || !host) {
    throw new Error(
      "Genie needs DATABRICKS_TOKEN (or DBT_ACCESS_TOKEN), or OAuth client id/secret + DATABRICKS_HOST"
    );
  }

  const res = await fetch(`https://${host}/oidc/v1/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: clientId,
      client_secret: clientSecret,
      scope: "all-apis",
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`OAuth token failed (${res.status}): ${body}`);
  }
  const json = await res.json();
  cachedOauth = {
    token: json.access_token,
    expires: Date.now() + Math.max(30, (json.expires_in || 3600) - 60) * 1000,
  };
  return cachedOauth.token;
}

async function genieFetch(path, { method = "GET", body } = {}) {
  const host = workspaceHost();
  if (!host) throw new Error("Set DATABRICKS_HOST");
  if (!SPACE_ID) throw new Error("Set GENIE_SPACE_ID");

  const token = await workspaceToken();
  const res = await fetch(`https://${host}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }
  if (!res.ok) {
    const msg = json?.message || json?.error || text || res.statusText;
    const err = new Error(`Genie API ${res.status}: ${msg}`);
    err.status = res.status;
    err.body = json;
    throw err;
  }
  return json;
}

export function genieSpaceId() {
  return SPACE_ID;
}

export function briefPrompt(team, season, opts = {}) {
  return BRIEF_SINGLE_PROMPT(team, season, opts);
}

export function briefFactsPrompt(team, season, qbNote = null) {
  return BRIEF_FACTS_PROMPT(team, season, qbNote);
}

export function briefNarrativePrompt(team, season, opts = {}) {
  return BRIEF_NARRATIVE_PROMPT(team, season, opts);
}

/**
 * Returning QB starter(s) from gold qb_room — used to keep high-profile
 * returners (e.g. Arch Manning) from being dropped when Genie focuses on portal.
 */
export async function getReturningQbNote(team, season) {
  const safeTeam = esc(team);
  try {
    const rows = await query(`
      SELECT
        first_name,
        last_name,
        qb_class,
        is_returning_starter,
        prior_pass_yds
      FROM ${gold("qb_room")}
      WHERE season = ${Number(season)}
        AND team = '${safeTeam}'
        AND COALESCE(is_returning_starter, false) = true
      ORDER BY COALESCE(prior_pass_yds, 0) DESC, COALESCE(career_pass_yds, 0) DESC
      LIMIT 2
    `);
    if (!rows.length) return null;
    // Keep this as plain names — labels like qb_class make prompts sound robotic.
    return rows
      .map((r) => `${r.first_name || ""} ${r.last_name || ""}`.trim())
      .filter(Boolean)
      .join(" and ");
  } catch {
    return null;
  }
}

/** Normalize conversation/message ids across start-conversation and create-message shapes. */
export function messageIds(payload, fallbackConversationId = null) {
  const conversationId =
    payload?.conversation?.id ||
    payload?.conversation_id ||
    payload?.message?.conversation_id ||
    fallbackConversationId ||
    null;
  const messageId =
    payload?.message?.message_id ||
    payload?.message?.id ||
    payload?.message_id ||
    payload?.id ||
    null;
  return { conversationId, messageId };
}

export async function startConversation(content) {
  return genieFetch(`/api/2.0/genie/spaces/${SPACE_ID}/start-conversation`, {
    method: "POST",
    body: { content },
  });
}

export async function createMessage(conversationId, content) {
  return genieFetch(
    `/api/2.0/genie/spaces/${SPACE_ID}/conversations/${conversationId}/messages`,
    { method: "POST", body: { content } }
  );
}

export async function getMessage(conversationId, messageId) {
  return genieFetch(
    `/api/2.0/genie/spaces/${SPACE_ID}/conversations/${conversationId}/messages/${messageId}`
  );
}

/**
 * Pull plain-text answer from a completed Genie message.
 * Prefer explicit text attachments (last wins) over incidental content fields —
 * Genie often returns query + suggested_questions + text in that order.
 */
export function extractText(message) {
  const attachments = message?.attachments;
  if (!Array.isArray(attachments)) return null;

  let best = null;
  for (const att of attachments) {
    const content = att?.text?.content ?? att?.text?.value;
    if (typeof content === "string" && content.trim()) {
      best = content;
    }
  }
  if (best) return cleanGenieText(best);

  for (const att of attachments) {
    const content = att?.content;
    if (typeof content === "string" && content.trim()) {
      return cleanGenieText(content);
    }
  }
  return null;
}

/**
 * Build the content Genie sees for Ask Genie.
 * Keep phrasing close to what a user would type in the Databricks Genie UI —
 * avoid "season preview" wrappers that bias Genie toward a different SQL path.
 */
export function chatContent({ question, team, season, conversationId }) {
  const q = String(question || "").trim();
  if (!q) return q;
  // Follow-ups already have conversation context.
  if (conversationId) return q;
  if (!team) return q;

  const teamLc = String(team).toLowerCase();
  if (q.toLowerCase().includes(teamLc)) return q;
  return `${q} for ${team} in ${season}`;
}

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"]);

export function isTerminalStatus(status) {
  return TERMINAL.has(String(status || "").toUpperCase());
}

export async function waitForMessage(
  conversationId,
  messageId,
  { timeoutMs = 240000, intervalMs = 2500 } = {}
) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const msg = await getMessage(conversationId, messageId);
    const status = String(msg?.status || "").toUpperCase();
    if (status === "COMPLETED") {
      return { ok: true, message: msg, text: extractText(msg) };
    }
    if (status === "FAILED" || status === "CANCELLED") {
      const errDetail = msg?.error?.error || msg?.error?.message || status;
      return { ok: false, message: msg, error: errDetail };
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return { ok: false, error: "Genie timed out waiting for a response" };
}

export async function askGenieAndWait(content, opts) {
  const started = await startConversation(content);
  const { conversationId, messageId } = messageIds(started);
  if (!conversationId || !messageId) {
    throw new Error("Genie start-conversation missing conversation/message ids");
  }
  const waited = await waitForMessage(conversationId, messageId, opts);
  return { conversationId, messageId, ...waited };
}

function looksLikeClarifying(text) {
  const t = String(text || "");
  return /would you prefer|which would you like|can you clarify|more specific/i.test(
    t
  );
}

/**
 * Generate a polished team brief: player facts → narrative (max 4 sentences).
 * Injects returning-QB + optional schedule context so high-profile returners
 * are not dropped when Genie over-indexes on portal moves.
 */
export async function generateTeamBrief(team, season, opts) {
  const [scheduleNote, qbNote] = await Promise.all([
    getScheduleCompetitionNote(team, season),
    getReturningQbNote(team, season),
  ]);
  const ctx = { scheduleNote, qbNote };

  const factsPrompt = briefFactsPrompt(team, season, qbNote);
  let facts = await askGenieAndWait(factsPrompt, opts);
  // One retry — Genie sometimes returns a thin/clarify-y first pass on portal+QB asks.
  if (!facts.ok || !facts.text || looksLikeClarifying(facts.text)) {
    facts = await askGenieAndWait(factsPrompt, opts);
  }
  if (!facts.ok || !facts.text || looksLikeClarifying(facts.text)) {
    const fallbackPrompt = briefPrompt(team, season, ctx);
    const fallback = await askGenieAndWait(fallbackPrompt, opts);
    return {
      ...fallback,
      prompt: fallbackPrompt,
      mode: "single_fallback",
      ...ctx,
    };
  }

  const narrativePrompt = briefNarrativePrompt(team, season, ctx);
  const started = await createMessage(facts.conversationId, narrativePrompt);
  const { conversationId, messageId } = messageIds(
    started,
    facts.conversationId
  );
  if (!conversationId || !messageId) {
    const fallbackPrompt = briefPrompt(team, season, ctx);
    const fallback = await askGenieAndWait(fallbackPrompt, opts);
    return {
      ...fallback,
      prompt: fallbackPrompt,
      mode: "single_fallback",
      ...ctx,
    };
  }

  const narrative = await waitForMessage(conversationId, messageId, opts);
  if (
    !narrative.ok ||
    !narrative.text ||
    looksLikeClarifying(narrative.text)
  ) {
    const fallbackPrompt = briefPrompt(team, season, ctx);
    const fallback = await askGenieAndWait(fallbackPrompt, opts);
    return {
      ...fallback,
      prompt: fallbackPrompt,
      mode: "single_fallback",
      ...ctx,
    };
  }

  return {
    ok: true,
    text: narrative.text,
    conversationId,
    messageId,
    message: narrative.message,
    prompt: `${factsPrompt}\n---\n${narrativePrompt}`,
    mode: "two_step",
    factsText: facts.text,
    ...ctx,
  };
}

export async function getStoredBrief(season, team) {
  const key = `${season}::${team}`;
  const hit = briefMemCache.get(key);
  if (hit) return hit;

  const rows = await query(`
    SELECT season, team, prompt, brief_text, conversation_id, message_id, space_id, generated_at
    FROM ${appTable("genie_team_briefs")}
    WHERE season = ${Number(season)}
      AND team = '${esc(team)}'
    LIMIT 1
  `);
  const row = rows[0] || null;
  const payload = row
    ? {
        season: row.season,
        team: row.team,
        prompt: row.prompt,
        text: cleanGenieText(row.brief_text) || null,
        status: row.brief_text ? "ready" : "pending",
        generatedAt: row.generated_at || null,
        conversationId: row.conversation_id || null,
        messageId: row.message_id || null,
      }
    : { season, team, status: "missing", text: null };

  if (payload.status === "ready") briefMemCache.set(key, payload);
  return payload;
}

export async function upsertBrief({
  season,
  team,
  prompt,
  briefText,
  conversationId,
  messageId,
}) {
  const safeTeam = esc(team);
  const safePrompt = esc(prompt);
  const safeText = esc(cleanGenieText(briefText) || briefText);
  const safeConv = esc(conversationId || "");
  const safeMsg = esc(messageId || "");
  const safeSpace = esc(SPACE_ID);

  await query(`
    MERGE INTO ${appTable("genie_team_briefs")} AS t
    USING (
      SELECT
        ${Number(season)} AS season,
        '${safeTeam}' AS team,
        '${safePrompt}' AS prompt,
        '${safeText}' AS brief_text,
        '${safeConv}' AS conversation_id,
        '${safeMsg}' AS message_id,
        '${safeSpace}' AS space_id,
        current_timestamp() AS generated_at
    ) AS s
    ON t.season = s.season AND t.team = s.team
    WHEN MATCHED THEN UPDATE SET
      prompt = s.prompt,
      brief_text = s.brief_text,
      conversation_id = s.conversation_id,
      message_id = s.message_id,
      space_id = s.space_id,
      generated_at = s.generated_at
    WHEN NOT MATCHED THEN INSERT (
      season, team, prompt, brief_text, conversation_id, message_id, space_id, generated_at
    ) VALUES (
      s.season, s.team, s.prompt, s.brief_text, s.conversation_id, s.message_id, s.space_id, s.generated_at
    )
  `);

  briefMemCache.clear();
}

export async function listBriefTeams(season = previewSeason()) {
  try {
    const rows = await query(`
      SELECT DISTINCT team
      FROM ${appTable("genie_team_briefs")}
      WHERE season = ${Number(season)}
      ORDER BY team
    `);
    if (rows.length) return rows.map((r) => r.team);
  } catch {
    // Table may not exist yet before dbt run.
  }

  const fromGold = await query(`
    SELECT DISTINCT team
    FROM ${gold("returning_production_team")}
    WHERE season = ${Number(season)}
      AND conference IS NOT NULL
    ORDER BY team
  `);
  return fromGold.map((r) => r.team);
}

export { previewSeason };
