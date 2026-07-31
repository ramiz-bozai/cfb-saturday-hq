/**
 * Upcoming-schedule difficulty from silver games + prior-season SP+.
 * Returns null when the season's schedule is not loaded yet.
 */
import { esc, query, silver } from "./db.js";

function difficultyBand(avgOppSp) {
  if (avgOppSp == null || !Number.isFinite(avgOppSp)) return null;
  if (avgOppSp >= 10) {
    return { key: "brutal", label: "Brutal slate", tone: "danger" };
  }
  if (avgOppSp >= 3) {
    return { key: "hard", label: "Hard slate", tone: "amber" };
  }
  if (avgOppSp >= -3) {
    return { key: "average", label: "Average slate", tone: "muted" };
  }
  return { key: "soft", label: "Softer slate", tone: "ok" };
}

/**
 * @returns {Promise<null | {
 *   available: true,
 *   season: number,
 *   priorSeason: number,
 *   games: number,
 *   ratedOpponents: number,
 *   avgOppSp: number | null,
 *   toughestOpponent: string | null,
 *   toughestOppSp: number | null,
 *   conferences: string[],
 *   band: string | null,
 *   label: string,
 *   tone: string,
 *   tip: string,
 *   note: string,
 * }>}
 */
export async function getScheduleDifficulty(team, season) {
  const safeTeam = esc(team);
  const year = Number(season);
  const priorSeason = year - 1;
  try {
    const rows = await query(`
      WITH sched AS (
        SELECT
          CASE WHEN g.home_team = '${safeTeam}' THEN g.away_team ELSE g.home_team END AS opponent,
          CASE WHEN g.home_team = '${safeTeam}' THEN g.away_conference ELSE g.home_conference END AS opp_conference,
          g.week,
          g.start_date
        FROM ${silver("games")} AS g
        WHERE g.season = ${year}
          AND g.season_type = 'regular'
          AND (g.home_team = '${safeTeam}' OR g.away_team = '${safeTeam}')
      ),
      opp_sp AS (
        SELECT team, sp_overall, sp_rank
        FROM ${silver("sp_plus")}
        WHERE season = ${priorSeason}
      )
      SELECT
        COUNT(*) AS games,
        COUNT(s.sp_overall) AS rated_opponents,
        AVG(s.sp_overall) AS avg_opp_sp,
        MAX(s.sp_overall) AS toughest_opp_sp,
        MAX_BY(sc.opponent, COALESCE(s.sp_overall, -999)) AS toughest_opponent,
        SORT_ARRAY(COLLECT_SET(sc.opp_conference)) AS conferences
      FROM sched AS sc
      LEFT JOIN opp_sp AS s ON s.team = sc.opponent
    `);
    const row = rows[0];
    const games = Number(row?.games || 0);
    if (!games) return null;

    const ratedOpponents = Number(row?.rated_opponents || 0);
    const avgOppSp =
      row?.avg_opp_sp != null && Number.isFinite(Number(row.avg_opp_sp))
        ? Number(row.avg_opp_sp)
        : null;
    const toughestOppSp =
      row?.toughest_opp_sp != null && Number.isFinite(Number(row.toughest_opp_sp))
        ? Number(row.toughest_opp_sp)
        : null;
    const toughestOpponent = row?.toughest_opponent || null;
    const conferences = Array.isArray(row?.conferences)
      ? row.conferences.filter(Boolean)
      : [];

    const bandInfo = difficultyBand(avgOppSp);
    const label = bandInfo?.label || "Schedule loaded";
    const tone = bandInfo?.tone || "muted";

    const tipParts = [
      `${games} regular-season games on the ${year} slate.`,
      avgOppSp != null
        ? `Avg prior-season (${priorSeason}) SP+ of rated opponents: ${avgOppSp.toFixed(1)}.`
        : "Opponent SP+ not available yet for difficulty rating.",
      toughestOpponent
        ? `Toughest rated opponent by prior SP+: ${toughestOpponent}${
            toughestOppSp != null ? ` (${toughestOppSp.toFixed(1)})` : ""
          }.`
        : null,
      "Higher opponent SP+ = harder slate. Not gambling advice.",
    ].filter(Boolean);

    const noteParts = [`${games} regular-season games`];
    if (conferences.length) {
      noteParts.push(`conferences on the slate: ${conferences.join(", ")}`);
    }
    if (ratedOpponents > 0 && avgOppSp != null) {
      const bandWord =
        avgOppSp >= 10
          ? "very hard"
          : avgOppSp >= 3
            ? "above-average"
            : avgOppSp >= -3
              ? "mixed / middle-of-the-pack"
              : "comparatively softer";
      noteParts.push(
        `avg prior-season (${priorSeason}) SP+ of rated opponents ≈ ${avgOppSp.toFixed(1)} (${bandWord})`
      );
    }
    if (toughestOpponent) {
      noteParts.push(`toughest rated opponent by prior SP+: ${toughestOpponent}`);
    }

    return {
      available: true,
      season: year,
      priorSeason,
      games,
      ratedOpponents,
      avgOppSp,
      toughestOpponent,
      toughestOppSp,
      conferences,
      band: bandInfo?.key || null,
      label,
      tone,
      tip: tipParts.join(" "),
      note: noteParts.join("; "),
    };
  } catch {
    return null;
  }
}

/** Genie-friendly one-liner; null when schedule is missing. */
export async function getScheduleCompetitionNote(team, season) {
  const d = await getScheduleDifficulty(team, season);
  return d?.note || null;
}
