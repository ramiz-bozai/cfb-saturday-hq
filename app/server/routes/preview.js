import { Router } from "express";
import { gold, silver, query, esc, previewSeason, createTtlCache } from "../db.js";
import { getScheduleDifficulty } from "../scheduleDifficulty.js";

const router = Router();

/** Team preview payloads change rarely within a session — cache for 10 minutes. */
const teamCache = createTtlCache(10 * 60 * 1000);

function teamLogoUrl(logos) {
  const list = Array.isArray(logos) ? logos : [];
  const preferred =
    list.find((u) => typeof u === "string" && u && !u.includes("-dark")) || list[0] || null;
  return preferred ? String(preferred).replace(/^http:\/\//i, "https://") : null;
}

/** Parse a Databricks column that may already be an object or a JSON string. */
function parseJsonCol(value) {
  if (value == null || value === "") return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

router.get("/meta", (_req, res) => {
  res.json({ previewSeason: previewSeason() });
});

router.get("/teams", async (req, res, next) => {
  try {
    const season = Number(req.query.season || previewSeason());
    const rows = await query(`
      SELECT DISTINCT team
      FROM ${gold("returning_production_team")}
      WHERE season = ${season}
        AND conference IS NOT NULL
      ORDER BY team
    `);
    res.json(rows.map((r) => r.team));
  } catch (err) {
    next(err);
  }
});

router.get("/overview", async (req, res, next) => {
  try {
    const season = Number(req.query.season || previewSeason());
    const conference = String(req.query.conference || "").trim();
    const confClause = conference ? `AND conference = '${esc(conference)}'` : "";
    const confJoin = conference ? `AND r.conference = '${esc(conference)}'` : "";

    const [returning, dependency, portalWinners, portalLosers, risks, qbRooms, conferences] =
      await Promise.all([
        query(`
          SELECT team, conference,
                 percent_ppa, percent_offense_returning, percent_defense_returning,
                 percent_usage, percent_production, percent_sacks, source
          FROM ${gold("returning_production_team")}
          WHERE season = ${season}
            AND conference IS NOT NULL
            AND coalesce(percent_offense_returning, percent_defense_returning) IS NOT NULL
          ${confClause}
          ORDER BY (
            coalesce(percent_offense_returning, 1.0)
            + coalesce(percent_defense_returning, 1.0)
          ) ASC
          LIMIT 8
        `),
        query(`
          SELECT d.team, d.transfer_dependency_score, d.pct_usage_from_transfers,
                 d.critical_units_on_transfers, d.impact_additions, d.impact_losses
          FROM ${gold("transfer_dependency")} d
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = d.season AND r.team = d.team
          WHERE d.season = ${season}
          ${confJoin}
          ORDER BY d.transfer_dependency_score DESC
          LIMIT 10
        `),
        query(`
          SELECT p.team, p.impact_additions, p.depth_additions, p.impact_losses, p.depth_losses,
                 p.net_offense_production_gained, p.net_defense_production_gained,
                 p.net_talent_gained,
                 p.projected_starters_added, p.projected_starters_lost, p.avg_continuity_score
          FROM ${gold("portal_team_ledger")} p
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = p.season AND r.team = p.team
          WHERE p.season = ${season}
          ${confJoin}
          ORDER BY p.net_offense_production_gained DESC NULLS LAST
          LIMIT 8
        `),
        query(`
          SELECT p.team, p.impact_additions, p.depth_additions, p.impact_losses, p.depth_losses,
                 p.net_offense_production_gained, p.net_defense_production_gained,
                 p.net_talent_gained,
                 p.projected_starters_added, p.projected_starters_lost, p.avg_continuity_score
          FROM ${gold("portal_team_ledger")} p
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = p.season AND r.team = p.team
          WHERE p.season = ${season}
          ${confJoin}
          ORDER BY p.net_offense_production_gained ASC NULLS LAST
          LIMIT 8
        `),
        query(`
          SELECT rr.team, rr.position_group, rr.replacement_risk, rr.metric_name,
                 rr.departed_share, rr.best_returner_metric, rr.continuity_score, rr.callout
          FROM ${gold("replacement_risk")} rr
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = rr.season AND r.team = rr.team
          WHERE rr.season = ${season}
          ${confJoin}
          ORDER BY coalesce(rr.departed_share, 0) DESC, rr.continuity_score ASC
          LIMIT 12
        `),
        query(`
          SELECT q.team, q.room_class, count(*) AS qbs
          FROM ${gold("qb_room")} q
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = q.season AND r.team = q.team
          WHERE q.season = ${season}
          ${confJoin}
          GROUP BY q.team, q.room_class
        `),
        query(`
          SELECT DISTINCT conference
          FROM ${gold("returning_production_team")}
          WHERE season = ${season} AND conference IS NOT NULL
          ORDER BY conference
        `),
      ]);

    res.json({
      season,
      conferences: conferences.map((c) => c.conference),
      thinnestReturning: returning,
      transferDependent: dependency,
      portalWinners,
      portalLosers,
      risks,
      qbRooms,
    });
  } catch (err) {
    next(err);
  }
});

router.get("/team/:team", async (req, res, next) => {
  try {
    const season = Number(req.query.season || previewSeason());
    const team = String(req.params.team);
    const cacheKey = teamCacheKey(season, team);
    const cached = teamCache.get(cacheKey);
    if (cached) {
      res.set("X-Cache", "HIT");
      return res.json(cached);
    }

    const { payload } = await loadTeamPayload(season, team);
    res.set("X-Cache", "MISS");
    res.json(payload);
  } catch (err) {
    next(err);
  }
});

function teamCacheKey(season, team) {
  return `v9::${season}::${team}`;
}

async function loadTeamPayload(season, team) {
  const cacheKey = teamCacheKey(season, team);
  const cached = teamCache.get(cacheKey);
  if (cached) return { payload: cached, cache: "HIT" };

  const safe = esc(team);
  const priorSeason = season - 1;

  const rows = await query(`
      SELECT
        (SELECT to_json(struct(*))
           FROM ${gold("returning_production_team")}
          WHERE season = ${season} AND team = '${safe}'
          LIMIT 1) AS returning_json,
        (SELECT to_json(struct(*))
           FROM ${gold("portal_team_ledger")}
          WHERE season = ${season} AND team = '${safe}'
          LIMIT 1) AS ledger_json,
        (SELECT to_json(struct(*))
           FROM ${gold("transfer_dependency")}
          WHERE season = ${season} AND team = '${safe}'
          LIMIT 1) AS dependency_json,
        (SELECT to_json(struct(
            logos, color, alternate_color, abbreviation, conference
          ))
           FROM ${silver("teams")}
          WHERE team = '${safe}'
          LIMIT 1) AS team_meta_json,
        (SELECT to_json(struct(
            signees, rated_signees, avg_stars, four_stars, five_stars, avg_rating, class_rank
          ))
           FROM ${gold("hs_recruiting_class")}
          WHERE season = ${season} AND team = '${safe}'
          LIMIT 1) AS hs_class_json,
        (SELECT to_json(collect_list(named_struct(
            'player_name', player_name,
            'position', position,
            'position_group', position_group,
            'stars', stars,
            'rating', rating,
            'recruiting_rank', recruiting_rank,
            'high_school', high_school,
            'city', city,
            'state_province', state_province,
            'recruit_type', recruit_type
          )))
           FROM (
             SELECT
               player_name, position, position_group, stars, rating,
               recruiting_rank, high_school, city, state_province, recruit_type
             FROM ${silver("recruiting_players")}
             WHERE class_year = ${season}
               AND committed_to = '${safe}'
               AND lower(coalesce(recruit_type, 'HighSchool')) IN ('highschool', 'high school')
             ORDER BY coalesce(rating, 0) DESC, coalesce(stars, 0) DESC, coalesce(recruiting_rank, 99999)
           ) AS hs_sorted
          ) AS hs_recruits_json,
        (SELECT max(roster_source)
           FROM ${gold("roster_snapshot")}
          WHERE season = ${season} AND team = '${safe}') AS roster_source,
        (SELECT to_json(struct(wins, losses, games_played))
           FROM ${gold("team_week")}
          WHERE season = ${priorSeason} AND team = '${safe}'
          ORDER BY week DESC
          LIMIT 1) AS prior_record_json,
        (SELECT to_json(collect_list(named_struct(
            'position_group', position_group,
            'continuity_score', continuity_score,
            'production_returning_pct', production_returning_pct,
            'usage_returning_pct', usage_returning_pct,
            'impact_additions', impact_additions,
            'impact_losses', impact_losses,
            'depth_additions', depth_additions,
            'depth_losses', depth_losses,
            'net_production_gained', net_production_gained,
            'talent_returning', talent_returning,
            'talent_added', talent_added,
            'talent_lost', talent_lost,
            'net_talent_gained', net_talent_gained,
            'projected_starters_added', projected_starters_added,
            'projected_starters_lost', projected_starters_lost,
            'replacement_risk', replacement_risk
          )))
           FROM ${gold("unit_continuity")}
          WHERE season = ${season} AND team = '${safe}') AS units_json,
        (SELECT to_json(collect_list(named_struct(
            'position_group', position_group,
            'replacement_risk', replacement_risk,
            'metric_name', metric_name,
            'departed_share', departed_share,
            'best_returner_metric', best_returner_metric,
            'continuity_score', continuity_score,
            'callout', callout
          )))
           FROM ${gold("replacement_risk")}
          WHERE season = ${season} AND team = '${safe}') AS risks_json,
        (SELECT to_json(collect_list(named_struct(
            'first_name', first_name,
            'last_name', last_name,
            'position_group', position_group,
            'origin', origin,
            'destination', destination,
            'impact_class', impact_class,
            'projected_starter', projected_starter,
            'prior_usage_overall', prior_usage_overall,
            'prior_production_score', prior_production_score,
            'talent_score', talent_score,
            'transfer_stars', transfer_stars
          )))
           FROM ${gold("portal_moves")}
          WHERE season = ${season}
            AND (origin = '${safe}' OR destination = '${safe}')) AS moves_json,
        (SELECT to_json(collect_list(named_struct(
            'first_name', first_name,
            'last_name', last_name,
            'qb_class', qb_class,
            'room_class', room_class,
            'qb_rank', qb_rank,
            'is_returning_starter', is_returning_starter,
            'is_backup', is_backup,
            'is_transfer_addition', is_transfer_addition,
            'prior_pass_att', prior_pass_att,
            'career_pass_att', career_pass_att,
            'career_avg_ppa_weighted', career_avg_ppa_weighted,
            'avg_ppa_all', avg_ppa_all,
            'turnover_rate', turnover_rate,
            'career_rush_yds', career_rush_yds,
            'transfer_count', transfer_count,
            'last_transfer_origin', last_transfer_origin,
            'stars', stars,
            'recruiting_rating', recruiting_rating,
            'roster_source', roster_source
          )))
           FROM ${gold("qb_room")}
          WHERE season = ${season} AND team = '${safe}') AS qbs_json
  `);

  const row = rows[0] || {};
  const returning = parseJsonCol(row.returning_json);
  const ledger = parseJsonCol(row.ledger_json);
  const dependency = parseJsonCol(row.dependency_json);
  const meta = parseJsonCol(row.team_meta_json) || {};
  const hsClass = parseJsonCol(row.hs_class_json);
  const prior = parseJsonCol(row.prior_record_json);
  let units = parseJsonCol(row.units_json) || [];
  let risks = parseJsonCol(row.risks_json) || [];
  let moves = parseJsonCol(row.moves_json) || [];
  let qbs = parseJsonCol(row.qbs_json) || [];
  let hsRecruits = parseJsonCol(row.hs_recruits_json) || [];

  units = [...units].sort(
    (a, b) => Number(a.continuity_score ?? 999) - Number(b.continuity_score ?? 999)
  );
  risks = [...risks].sort((a, b) => {
    const ds = Number(b.departed_share ?? 0) - Number(a.departed_share ?? 0);
    if (ds !== 0) return ds;
    return Number(a.continuity_score ?? 999) - Number(b.continuity_score ?? 999);
  });
  moves = [...moves].sort((a, b) => {
    const aOl = a.position_group === "OL" ? 1 : 0;
    const bOl = b.position_group === "OL" ? 1 : 0;
    if (aOl !== bOl) return aOl - bOl;
    return (
      Number(b.prior_production_score ?? -1e9) - Number(a.prior_production_score ?? -1e9)
    );
  });
  qbs = [...qbs].sort((a, b) => Number(a.qb_rank ?? 999) - Number(b.qb_rank ?? 999));
  hsRecruits = [...hsRecruits].sort((a, b) => {
    const rating = Number(b.rating ?? 0) - Number(a.rating ?? 0);
    if (rating !== 0) return rating;
    const stars = Number(b.stars ?? 0) - Number(a.stars ?? 0);
    if (stars !== 0) return stars;
    return Number(a.recruiting_rank ?? 99999) - Number(b.recruiting_rank ?? 99999);
  });

  const scheduleDifficulty = await getScheduleDifficulty(team, season);

  const payload = {
    season,
    team,
    logoUrl: teamLogoUrl(meta.logos),
    teamColor: meta.color || null,
    abbreviation: meta.abbreviation || null,
    conference: meta.conference || returning?.conference || null,
    rosterSource: row.roster_source || "constructed",
    priorRecord: prior
      ? {
          season: priorSeason,
          wins: prior.wins,
          losses: prior.losses,
          gamesPlayed: prior.games_played,
        }
      : null,
    scheduleDifficulty,
    returning: returning || null,
    units,
    ledger: ledger || null,
    dependency: dependency || null,
    risks,
    moves,
    qbs,
    roomClass: qbs[0]?.room_class || null,
    hsClass: hsClass || null,
    hsRecruits,
  };
  teamCache.set(cacheKey, payload);
  return { payload, cache: "MISS" };
}

/**
 * Background-warm the in-memory team cache for the preview season.
 * Runs with limited concurrency so the warehouse is not flooded.
 */
export async function warmPreviewTeamCache(season = previewSeason(), concurrency = 4) {
  const t0 = Date.now();
  const teams = await query(`
    SELECT DISTINCT team
    FROM ${gold("returning_production_team")}
    WHERE season = ${Number(season)}
      AND conference IS NOT NULL
    ORDER BY team
  `);
  const names = teams.map((r) => r.team).filter(Boolean);
  let done = 0;
  let failed = 0;
  let i = 0;

  async function worker() {
    while (i < names.length) {
      const idx = i++;
      const name = names[idx];
      try {
        await loadTeamPayload(season, name);
        done += 1;
      } catch (err) {
        failed += 1;
        console.error(`Preview cache warm failed for ${name}:`, err.message || err);
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, names.length) }, () => worker()));
  console.log(
    `Preview team cache warm: ${done}/${names.length} teams` +
      (failed ? ` (${failed} failed)` : "") +
      ` in ${((Date.now() - t0) / 1000).toFixed(1)}s`
  );
  return { done, failed, total: names.length };
}

export default router;
