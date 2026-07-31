import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  QB_CLASS_ORDER,
  bandFromScore,
  fmtInt,
  fmtNum,
  fmtPct,
  qbTone,
  riskTone,
  unitLabel,
} from "../labels";
import { Metric, Pill } from "../components/ui";

type Overview = {
  season: number;
  conferences: string[];
  thinnestReturning: any[];
  transferDependent: any[];
  portalWinners: any[];
  portalLosers: any[];
  risks: any[];
  qbRooms: { team: string; room_class: string; qbs: number }[];
};

export default function PreviewOverview() {
  const [season, setSeason] = useState<number | null>(null);
  const [conference, setConference] = useState("");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{ previewSeason: number }>("/api/preview/meta")
      .then((m) => setSeason(m.previewSeason))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (season == null) return;
    setLoading(true);
    const q = new URLSearchParams({ season: String(season) });
    if (conference) q.set("conference", conference);
    api<Overview>(`/api/preview/overview?${q}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, conference]);

  const qbGrouped = useMemo(() => {
    if (!data) return [];
    const map = new Map<string, string[]>();
    for (const row of data.qbRooms) {
      const list = map.get(row.room_class) || [];
      if (!list.includes(row.team)) list.push(row.team);
      map.set(row.room_class, list);
    }
    return QB_CLASS_ORDER.filter((c) => map.has(c)).map((c) => ({
      cls: c,
      teams: (map.get(c) || []).sort(),
    }));
  }, [data]);

  if (error) return <div className="empty">{error}</div>;
  if (loading || !data || season == null) return <div className="loading">Loading preview…</div>;

  return (
    <div>
      <section className="section">
        <h2>{season} Offseason Preview</h2>
        <p className="lede">
          Roster continuity, portal impact, and QB rooms — weighted by prior usage and
          production, not stars alone. Rosters are constructed when CFBD has not published
          the upcoming season yet (prior roster − portal − draft + arrivals).
        </p>
        <div className="controls">
          <div className="field">
            <label>Season</label>
            <input
              type="number"
              value={season}
              min={2015}
              max={2030}
              onChange={(e) => setSeason(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>Conference</label>
            <select value={conference} onChange={(e) => setConference(e.target.value)}>
              <option value="">All FBS</option>
              {data.conferences.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Team deep dive</label>
            <Link className="team-chip" to="/preview/team">
              Open team view →
            </Link>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Thinnest returning production</h2>
        <p className="lede">Teams bringing back the least prior production — offseason volatility.</p>
        <div className="card-grid">
          {data.thinnestReturning.map((row) => (
            <Link key={row.team} to={`/preview/team?team=${encodeURIComponent(row.team)}&season=${season}`} className="card">
              <h3>{row.team}</h3>
              <p className="meta">{row.conference || "—"}</p>
              <div className="metric-row">
                <Metric label="Offense" value={fmtPct(row.percent_offense_returning)} band={bandFromScore(row.percent_offense_returning)} />
                <Metric label="Defense" value={fmtPct(row.percent_defense_returning)} band={bandFromScore(row.percent_defense_returning)} />
                <Metric label="PPA" value={fmtPct(row.percent_ppa)} band={bandFromScore(row.percent_ppa)} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Most transfer dependent</h2>
        <p className="lede">How much of the roster’s prior usage now rides on portal arrivals.</p>
        <div className="card-grid">
          {data.transferDependent.map((row) => (
            <Link key={row.team} to={`/preview/team?team=${encodeURIComponent(row.team)}&season=${season}`} className="card">
              <h3>{row.team}</h3>
              <div className="metric-row">
                <Metric
                  label="Dependency"
                  value={`${fmtInt(row.transfer_dependency_score)} / 100`}
                  band={
                    Number(row.transfer_dependency_score) >= 70
                      ? "low"
                      : Number(row.transfer_dependency_score) >= 40
                        ? "mid"
                        : "high"
                  }
                />
                <Metric label="Usage from transfers" value={fmtPct(row.pct_usage_from_transfers)} />
                <Metric label="Critical units" value={fmtInt(row.critical_units_on_transfers)} />
              </div>
              <p className="meta" style={{ marginTop: "0.65rem" }}>
                Impact +{fmtInt(row.impact_additions)} / −{fmtInt(row.impact_losses)}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Portal winners and losers</h2>
        <p className="lede">Net prior production gained or lost through the portal (and draft exits on the loss side of continuity).</p>
        <div className="split">
          <div>
            <h3 style={{ marginTop: 0 }}>Winners</h3>
            <div className="card-grid">
              {data.portalWinners.map((row) => (
                <Link
                  key={row.team}
                  to={`/preview/team?team=${encodeURIComponent(row.team)}&season=${season}`}
                  className="card"
                >
                  <h3>{row.team}</h3>
                  <div className="metric-row">
                    <Metric label="Net production" value={fmtNum(row.net_production_gained)} band="high" />
                    <Metric label="Net talent" value={fmtNum(row.net_talent_gained, 2)} />
                  </div>
                  <p className="meta" style={{ marginTop: "0.5rem" }}>
                    Impact +{fmtInt(row.impact_additions)} / −{fmtInt(row.impact_losses)}
                  </p>
                </Link>
              ))}
            </div>
          </div>
          <div>
            <h3 style={{ marginTop: 0 }}>Losers</h3>
            <div className="card-grid">
              {data.portalLosers.map((row) => (
                <Link
                  key={row.team}
                  to={`/preview/team?team=${encodeURIComponent(row.team)}&season=${season}`}
                  className="card"
                >
                  <h3>{row.team}</h3>
                  <div className="metric-row">
                    <Metric label="Net production" value={fmtNum(row.net_production_gained)} band="low" />
                    <Metric label="Net talent" value={fmtNum(row.net_talent_gained, 2)} />
                  </div>
                  <p className="meta" style={{ marginTop: "0.5rem" }}>
                    Impact +{fmtInt(row.impact_additions)} / −{fmtInt(row.impact_losses)}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Hottest replacement risks</h2>
        <p className="lede">Departed production that returners have not covered — portal and NFL draft.</p>
        {data.risks.map((row, i) => (
          <div key={`${row.team}-${row.position_group}-${i}`} className={`alert ${row.replacement_risk === "elevated" ? "elevated" : ""}`}>
            <div className="title">
              {row.team} · {unitLabel(row.position_group)}{" "}
              <Pill tone={riskTone(row.replacement_risk)}>{row.replacement_risk || "risk"}</Pill>
            </div>
            <p>{row.callout}</p>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>QB rooms by uncertainty</h2>
        <p className="lede">Room classification from career attempts, PPA, and transfer profile.</p>
        {qbGrouped.map(({ cls, teams }) => (
          <div key={cls} className="qb-class-block">
            <h3>
              <Pill tone={qbTone(cls)}>{cls}</Pill>
              <span className="meta">{teams.length} teams</span>
            </h3>
            <div className="team-chip-row">
              {teams.map((t) => (
                <Link key={t} className="team-chip" to={`/preview/team?team=${encodeURIComponent(t)}&season=${season}`}>
                  {t}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
