import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtNum, fmtPct } from "../labels";

export function MatchupPage({
  season,
  seasonType,
  week,
}: {
  season: number;
  seasonType: string;
  week: number;
}) {
  const [games, setGames] = useState<any[]>([]);
  const [choice, setChoice] = useState("");
  const [card, setCard] = useState<any | null>(null);

  useEffect(() => {
    api<any[]>(`/api/slate?season=${season}&seasonType=${seasonType}&week=${week}`).then(
      (rows) => {
        setGames(rows);
        if (rows[0]) {
          const label = `${rows[0].away_team} @ ${rows[0].home_team}`;
          setChoice(label);
        }
      }
    );
  }, [season, seasonType, week]);

  useEffect(() => {
    if (!choice) return;
    const game = games.find((g) => `${g.away_team} @ ${g.home_team}` === choice);
    if (!game) return;
    api<any>(
      `/api/matchup?season=${season}&seasonType=${seasonType}&week=${week}&home=${encodeURIComponent(game.home_team)}&away=${encodeURIComponent(game.away_team)}`
    ).then(setCard);
  }, [choice, games, season, seasonType, week]);

  if (!games.length) return <div className="empty">No games for this week yet.</div>;

  const highlight = card
    ? [
        ["Home", card.home_team],
        ["Away", card.away_team],
        ["Model home win %", fmtPct(card.model_home_win_prob)],
        ["Market home win %", fmtPct(card.market_home_win_prob)],
        ["Model − market", fmtPct(card.model_minus_market)],
        ["Spread", card.market_spread ?? "-"],
        ["Prior SP+ diff", fmtNum(card.sp_overall_diff_prior)],
        ["Talent diff", fmtNum(card.talent_diff, 0)],
      ]
    : [];

  return (
    <section className="section">
      <h2>Matchup</h2>
      <div className="controls">
        <div className="field">
          <label>Game</label>
          <select value={choice} onChange={(e) => setChoice(e.target.value)}>
            {games.map((g) => {
              const label = `${g.away_team} @ ${g.home_team}`;
              return (
                <option key={g.game_id} value={label}>
                  {label}
                </option>
              );
            })}
          </select>
        </div>
      </div>
      {card && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            {card.away_team} at {card.home_team}
          </h3>
          <div className="table-wrap" style={{ border: "none" }}>
            <table>
              <tbody>
                {highlight.map(([k, v]) => (
                  <tr key={String(k)}>
                    <th style={{ width: "40%" }}>{k}</th>
                    <td>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export function ProjectionsPage({ season }: { season: number }) {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    api<any[]>(`/api/projections?season=${season}`).then(setRows);
  }, [season]);

  return (
    <section className="section">
      <h2>Season / playoff projections</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>Conference</th>
              <th>Mean wins</th>
              <th>Playoff odds</th>
              <th>Avg seed if in</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.team}>
                <td>{r.team}</td>
                <td>{r.conference}</td>
                <td>{fmtNum(r.mean_wins)}</td>
                <td>{fmtPct(r.playoff_odds)}</td>
                <td>{fmtNum(r.avg_seed_if_in)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function BriefPage({
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
  const options = myTeams.length ? myTeams : ["Alabama"];
  const [team, setTeam] = useState(options[0]);
  const [brief, setBrief] = useState<any | null>(null);

  useEffect(() => {
    api<any>(
      `/api/brief?season=${season}&seasonType=${seasonType}&week=${week}&team=${encodeURIComponent(team)}`
    ).then(setBrief);
  }, [season, seasonType, week, team]);

  return (
    <section className="section">
      <h2>Weekly brief</h2>
      <div className="controls">
        <div className="field">
          <label>Team</label>
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            {options.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>
      {!brief ? (
        <div className="empty">No brief for this team/week.</div>
      ) : (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{brief.headline}</h3>
          <p>{brief.summary}</p>
          <p className="meta">
            Model {fmtPct(brief.model_win_prob)} · Market {fmtPct(brief.market_win_prob)} · Spread{" "}
            {brief.market_spread ?? "-"}
          </p>
        </div>
      )}
    </section>
  );
}
