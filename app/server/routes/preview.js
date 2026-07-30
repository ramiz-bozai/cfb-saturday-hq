import { Router } from "express";
import { gold, query, esc, previewSeason } from "../db.js";

const router = Router();

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
            AND coalesce(percent_ppa, percent_production) IS NOT NULL
          ${confClause}
          ORDER BY coalesce(percent_ppa, percent_production) ASC
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
                 p.net_production_gained, p.net_talent_gained,
                 p.projected_starters_added, p.projected_starters_lost, p.avg_continuity_score
          FROM ${gold("portal_team_ledger")} p
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = p.season AND r.team = p.team
          WHERE p.season = ${season}
          ${confJoin}
          ORDER BY p.net_production_gained DESC NULLS LAST
          LIMIT 8
        `),
        query(`
          SELECT p.team, p.impact_additions, p.depth_additions, p.impact_losses, p.depth_losses,
                 p.net_production_gained, p.net_talent_gained,
                 p.projected_starters_added, p.projected_starters_lost, p.avg_continuity_score
          FROM ${gold("portal_team_ledger")} p
          LEFT JOIN ${gold("returning_production_team")} r
            ON r.season = p.season AND r.team = p.team
          WHERE p.season = ${season}
          ${confJoin}
          ORDER BY p.net_production_gained ASC NULLS LAST
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
    const safe = esc(team);

    const [returning, units, ledger, dependency, risks, moves, qbs] = await Promise.all([
      query(`
        SELECT *
        FROM ${gold("returning_production_team")}
        WHERE season = ${season} AND team = '${safe}'
      `),
      query(`
        SELECT position_group, continuity_score, production_returning_pct, usage_returning_pct,
               impact_additions, impact_losses, depth_additions, depth_losses,
               net_production_gained, talent_returning, talent_added, talent_lost,
               net_talent_gained, projected_starters_added, projected_starters_lost,
               replacement_risk
        FROM ${gold("unit_continuity")}
        WHERE season = ${season} AND team = '${safe}'
        ORDER BY continuity_score ASC
      `),
      query(`
        SELECT *
        FROM ${gold("portal_team_ledger")}
        WHERE season = ${season} AND team = '${safe}'
      `),
      query(`
        SELECT *
        FROM ${gold("transfer_dependency")}
        WHERE season = ${season} AND team = '${safe}'
      `),
      query(`
        SELECT position_group, replacement_risk, metric_name, departed_share,
               best_returner_metric, continuity_score, callout
        FROM ${gold("replacement_risk")}
        WHERE season = ${season} AND team = '${safe}'
        ORDER BY coalesce(departed_share, 0) DESC, continuity_score ASC
      `),
      query(`
        SELECT first_name, last_name, position_group, origin, destination,
               impact_class, projected_starter, prior_usage_overall, prior_production_score,
               transfer_stars
        FROM ${gold("portal_moves")}
        WHERE season = ${season}
          AND (origin = '${safe}' OR destination = '${safe}')
        ORDER BY prior_production_score DESC NULLS LAST
      `),
      query(`
        SELECT first_name, last_name, qb_class, room_class, qb_rank,
               is_returning_starter, is_backup, is_transfer_addition,
               prior_pass_att, career_pass_att, career_avg_ppa_weighted, avg_ppa_all,
               turnover_rate, career_rush_yds, transfer_count, last_transfer_origin,
               stars, recruiting_rating, roster_source
        FROM ${gold("qb_room")}
        WHERE season = ${season} AND team = '${safe}'
        ORDER BY qb_rank ASC
      `),
    ]);

    const rosterSource = await query(`
      SELECT max(roster_source) AS roster_source
      FROM ${gold("roster_snapshot")}
      WHERE season = ${season} AND team = '${safe}'
    `);

    res.json({
      season,
      team,
      rosterSource: rosterSource[0]?.roster_source || "constructed",
      returning: returning[0] || null,
      units,
      ledger: ledger[0] || null,
      dependency: dependency[0] || null,
      risks,
      moves,
      qbs,
      roomClass: qbs[0]?.room_class || null,
    });
  } catch (err) {
    next(err);
  }
});

export default router;
