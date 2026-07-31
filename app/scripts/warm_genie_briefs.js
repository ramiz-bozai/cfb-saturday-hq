/**
 * Warm Genie bottom-line briefs into cfb_app.genie_team_briefs.
 *
 * Usage (from app/):
 *   node scripts/warm_genie_briefs.js
 *   node scripts/warm_genie_briefs.js --team=Oklahoma
 *   node scripts/warm_genie_briefs.js --force --concurrency=2
 *   node scripts/warm_genie_briefs.js --limit=5
 *
 * Requires DATABRICKS_HOST + token, GENIE_SPACE_ID, and MODIFY on genie_team_briefs.
 * Run dbt model app_genie_team_briefs first so the table/skeleton rows exist.
 */
import {
  generateTeamBrief,
  listBriefTeams,
  previewSeason,
  upsertBrief,
  getStoredBrief,
} from "../server/genie.js";

function arg(name, fallback = null) {
  const hit = process.argv.find((a) => a.startsWith(`--${name}=`));
  if (hit) return hit.slice(name.length + 3);
  if (process.argv.includes(`--${name}`)) return true;
  return fallback;
}

async function mapPool(items, concurrency, fn) {
  const results = [];
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await fn(items[idx], idx);
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, items.length) }, () => worker())
  );
  return results;
}

async function main() {
  const season = Number(arg("season", previewSeason()));
  const onlyTeam = arg("team");
  const force = Boolean(arg("force", false));
  const concurrency = Math.max(1, Number(arg("concurrency", 2)));
  const limit = arg("limit") != null ? Number(arg("limit")) : null;

  let teams = onlyTeam ? [String(onlyTeam)] : await listBriefTeams(season);
  if (limit != null && Number.isFinite(limit)) teams = teams.slice(0, limit);

  console.log(
    `Warming Genie briefs for ${teams.length} team(s), season=${season}, concurrency=${concurrency}, force=${force}`
  );

  let ok = 0;
  let skipped = 0;
  let failed = 0;

  await mapPool(teams, concurrency, async (team) => {
    try {
      if (!force) {
        const existing = await getStoredBrief(season, team);
        if (existing.status === "ready" && existing.text) {
          skipped += 1;
          console.log(`skip ${team} (already ready)`);
          return;
        }
      }

      console.log(`genie ${team}…`);
      const result = await generateTeamBrief(team, season);
      if (!result.ok || !result.text) {
        failed += 1;
        console.error(`fail ${team}:`, result.error || "no text");
        return;
      }

      await upsertBrief({
        season,
        team,
        prompt: result.prompt,
        briefText: result.text,
        conversationId: result.conversationId,
        messageId: result.messageId,
      });
      ok += 1;
      console.log(
        `ok ${team} [${result.mode}] (${result.text.slice(0, 80).replace(/\s+/g, " ")}…)`
      );
    } catch (err) {
      failed += 1;
      console.error(`fail ${team}:`, err.message || err);
    }
  });

  console.log(`Done. ok=${ok} skipped=${skipped} failed=${failed}`);
  if (failed) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
