import { Router } from "express";
import { gold, appTable, query, esc, defaultSeason } from "../db.js";

const router = Router();

router.get("/profiles", async (_req, res, next) => {
  try {
    const rows = await query(`
      SELECT display_name, teams
      FROM ${appTable("demo_profiles")}
      ORDER BY display_name
    `);
    res.json(
      rows.map((r) => ({
        displayName: r.display_name,
        teams: Array.isArray(r.teams) ? r.teams : r.teams ? [...r.teams] : [],
      }))
    );
  } catch (err) {
    next(err);
  }
});

router.get("/slate", async (req, res, next) => {
  try {
    const season = Number(req.query.season || defaultSeason());
    const seasonType = String(req.query.seasonType || "regular").toLowerCase();
    const week = Number(req.query.week || 1);
    const rows = await query(`
      SELECT game_id, season_type, week, start_date, completed, neutral_site,
             home_team, away_team, home_conference, away_conference,
             home_points, away_points,
             model_home_win_prob,
             market_home_win_prob_novig AS market_home_win_prob,
             model_minus_market_home AS model_minus_market,
             market_spread,
             home_games_played, away_games_played,
             home_win_pct, away_win_pct,
             home_win_pct_fbs, away_win_pct_fbs,
             home_avg_margin_l3_fbs, away_avg_margin_l3_fbs,
             sp_overall_diff_prior, talent_diff
      FROM ${gold("matchup_card")}
      WHERE season = ${season}
        AND lower(season_type) = '${esc(seasonType)}'
        AND week = ${week}
      ORDER BY start_date, game_id
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
});

router.get("/matchup", async (req, res, next) => {
  try {
    const season = Number(req.query.season || defaultSeason());
    const seasonType = String(req.query.seasonType || "regular").toLowerCase();
    const week = Number(req.query.week || 1);
    const home = esc(req.query.home);
    const away = esc(req.query.away);
    const rows = await query(`
      SELECT *
      FROM ${gold("matchup_card")}
      WHERE season = ${season}
        AND lower(season_type) = '${esc(seasonType)}'
        AND week = ${week}
        AND home_team = '${home}' AND away_team = '${away}'
    `);
    res.json(rows[0] || null);
  } catch (err) {
    next(err);
  }
});

router.get("/projections", async (req, res, next) => {
  try {
    const season = Number(req.query.season || defaultSeason());
    const rows = await query(`
      SELECT team, conference, mean_wins, playoff_odds, avg_seed_if_in
      FROM ${gold("playoff_projections")}
      WHERE season = ${season}
      ORDER BY playoff_odds DESC
      LIMIT 40
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
});

router.get("/brief", async (req, res, next) => {
  try {
    const season = Number(req.query.season || defaultSeason());
    const seasonType = String(req.query.seasonType || "regular").toLowerCase();
    const week = Number(req.query.week || 1);
    const team = esc(req.query.team || "Alabama");
    const rows = await query(`
      SELECT game_id, season, season_type, week, team, opponent, is_home,
             headline, summary, model_win_prob, market_win_prob, market_spread
      FROM ${gold("weekly_brief")}
      WHERE season = ${season}
        AND lower(season_type) = '${esc(seasonType)}'
        AND week = ${week}
        AND team = '${team}'
    `);
    res.json(rows[0] || null);
  } catch (err) {
    next(err);
  }
});

export default router;
