import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { fmtPct } from "../labels";
import { Metric, Pill } from "../components/ui";

type Profile = { displayName: string; teams: string[] };

function interestScore(row: any): number {
  const model = Number(row.model_home_win_prob);
  const disagreement = Math.abs(Number(row.model_minus_market) || 0);
  const tossUp = Number.isNaN(model) ? 0 : 1 - 2 * Math.abs(model - 0.5);
  return tossUp + 1.5 * disagreement;
}

function record(row: any, side: "home" | "away"): string {
  const games = Number(row[`${side}_games_played`]);
  const winPct = Number(row[`${side}_win_pct`]);
  if (!games || Number.isNaN(winPct)) return Number(row.week) <= 1 ? "0-0" : "—";
  const wins = Math.round(games * winPct);
  return `${wins}-${Math.round(games) - wins}`;
}

function GameCard({ row, myTeams }: { row: any; myTeams: string[] }) {
  const home = row.home_team;
  const away = row.away_team;
  const model = Number(row.model_home_win_prob);
  const market = Number(row.market_home_win_prob);
  const completed = Boolean(row.completed);
  const tags: string[] = [];
  if (myTeams.includes(home) || myTeams.includes(away)) tags.push("My Team");
  if (!Number.isNaN(model) && Math.abs(model - 0.5) <= 0.08) tags.push("Toss-up");
  const fav =
    !Number.isNaN(model) ? (model >= 0.5 ? home : away) : null;
  const favProb = !Number.isNaN(model) ? Math.max(model, 1 - model) : null;

  return (
    <div className="card game-card">
      <p className="meta">{tags.join(" · ") || "Weekly matchup"}</p>
      <h3>
        {away} at {home}
      </h3>
      <p className="meta">
        {away} {record(row, "away")} · {home} {record(row, "home")}
      </p>
      {completed ? (
        <p className="pick">
          Final: {away} {row.away_points}, {home} {row.home_points}
        </p>
      ) : fav ? (
        <p className="pick">
          Saturday HQ pick: {fav} ({fmtPct(favProb)})
        </p>
      ) : (
        <p className="pick">Prediction not available yet</p>
      )}
      <div className="metric-row">
        <Metric label="Model" value={fmtPct(favProb)} />
        <Metric
          label="Market"
          value={
            Number.isNaN(market)
              ? "—"
              : fmtPct(Math.max(market, 1 - market))
          }
        />
        <Metric
          label="Spread"
          value={
            row.market_spread == null
              ? "—"
              : Number(row.market_spread) === 0
                ? "Pick'em"
                : `-${Math.abs(Number(row.market_spread))}`
          }
        />
      </div>
    </div>
  );
}

export default function SlatePage({
  season,
  seasonType,
  week,
  myTeams,
}: {
  season: number;
  seasonType: string;
  week: number;
  myTeams: string[];
}) {
  const [rows, setRows] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api<any[]>(
      `/api/slate?season=${season}&seasonType=${seasonType}&week=${week}`
    )
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, seasonType, week]);

  const { mine, other } = useMemo(() => {
    const scored = rows
      .map((r) => ({ ...r, _score: interestScore(r) }))
      .sort((a, b) => b._score - a._score);
    const mine = scored.filter(
      (r) => myTeams.includes(r.home_team) || myTeams.includes(r.away_team)
    );
    const other = scored.filter(
      (r) => !myTeams.includes(r.home_team) && !myTeams.includes(r.away_team)
    );
    return { mine, other };
  }, [rows, myTeams]);

  if (loading) return <div className="loading">Loading slate…</div>;
  if (error) return <div className="empty">{error}</div>;
  if (!rows.length) return <div className="empty">No games for this week yet.</div>;

  return (
    <div>
      <section className="section">
        <h2>
          {seasonType} Week {week} slate
        </h2>
        <p className="lede">
          Cards prioritize close games and model–market disagreements. Market percentages are
          de-vigged.
        </p>
      </section>
      {mine.length > 0 && (
        <section className="section">
          <h2>My Teams</h2>
          <div className="card-grid">
            {mine.map((r) => (
              <GameCard key={r.game_id} row={r} myTeams={myTeams} />
            ))}
          </div>
        </section>
      )}
      <section className="section">
        <h2>Games to Watch</h2>
        <div className="card-grid">
          {other.map((r) => (
            <GameCard key={r.game_id} row={r} myTeams={myTeams} />
          ))}
        </div>
      </section>
    </div>
  );
}

export function HomePage({ myTeams, profiles, profile, setProfile }: {
  myTeams: string[];
  profiles: Profile[];
  profile: string;
  setProfile: (v: string) => void;
}) {
  return (
    <section className="section">
      <h2>Welcome</h2>
      <p className="lede">
        Use <strong>Slate</strong> for model vs market, <strong>Matchup</strong> for a deep dive,{" "}
        <strong>Projections</strong> for win totals / playoff odds, <strong>Brief</strong> for
        writeups, and <strong>Season Preview</strong> for roster continuity heading into the year.
      </p>
      <div className="controls">
        <div className="field">
          <label>Demo profile</label>
          <select value={profile} onChange={(e) => setProfile(e.target.value)}>
            {profiles.map((p) => (
              <option key={p.displayName} value={p.displayName}>
                {p.displayName}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>My Teams</h3>
        <div className="team-chip-row">
          {myTeams.length ? (
            myTeams.map((t) => (
              <Pill key={t} tone="trust">
                {t}
              </Pill>
            ))
          ) : (
            <span className="meta">No teams on this profile</span>
          )}
        </div>
      </div>
    </section>
  );
}
