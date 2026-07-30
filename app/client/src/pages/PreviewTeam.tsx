import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import {
  bandFromScore,
  fmtInt,
  fmtNum,
  fmtPct,
  qbTone,
  riskTone,
  unitLabel,
} from "../labels";
import { Metric, Pill } from "../components/ui";

type TeamData = {
  season: number;
  team: string;
  rosterSource: string;
  roomClass: string | null;
  returning: any;
  units: any[];
  ledger: any;
  dependency: any;
  risks: any[];
  moves: any[];
  qbs: any[];
};

export default function PreviewTeam() {
  const [params, setParams] = useSearchParams();
  const [teams, setTeams] = useState<string[]>([]);
  const [season, setSeason] = useState<number | null>(
    params.get("season") ? Number(params.get("season")) : null
  );
  const [team, setTeam] = useState(params.get("team") || "");
  const [data, setData] = useState<TeamData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<{ previewSeason: number }>("/api/preview/meta").then((m) => {
      if (season == null) setSeason(m.previewSeason);
    });
  }, []);

  useEffect(() => {
    if (season == null) return;
    api<string[]>(`/api/preview/teams?season=${season}`).then((list) => {
      setTeams(list);
      if (!team && list.length) setTeam(list.includes("Alabama") ? "Alabama" : list[0]);
    });
  }, [season]);

  useEffect(() => {
    if (season == null || !team) return;
    setLoading(true);
    setError(null);
    setParams({ team, season: String(season) });
    api<TeamData>(`/api/preview/team/${encodeURIComponent(team)}?season=${season}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, team]);

  const arrivals = useMemo(
    () => (data?.moves || []).filter((m) => m.destination === data?.team),
    [data]
  );
  const departures = useMemo(
    () => (data?.moves || []).filter((m) => m.origin === data?.team && m.destination !== data?.team),
    [data]
  );

  const ret = data?.returning;
  const dep = data?.dependency;
  const led = data?.ledger;

  return (
    <div>
      <div className="controls">
        <div className="field">
          <label>Season</label>
          <input
            type="number"
            value={season ?? ""}
            min={2015}
            max={2030}
            onChange={(e) => setSeason(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Team</label>
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="empty">{error}</div>}
      {loading && <div className="loading">Loading team…</div>}
      {!loading && data && (
        <>
          <div className="hero-team">
            <h1>{data.team}</h1>
            {data.roomClass && <Pill tone={qbTone(data.roomClass)}>{data.roomClass}</Pill>}
            <Pill tone="muted">{data.rosterSource === "published" ? "Published roster" : "Constructed roster"}</Pill>
          </div>

          <section className="section">
            <h2>Returning production</h2>
            <div className="card">
              <div className="metric-row">
                <Metric label="Offense returning" value={fmtPct(ret?.percent_offense_returning)} band={bandFromScore(ret?.percent_offense_returning)} />
                <Metric label="Defense returning" value={fmtPct(ret?.percent_defense_returning)} band={bandFromScore(ret?.percent_defense_returning)} />
                <Metric label="PPA returning" value={fmtPct(ret?.percent_ppa)} band={bandFromScore(ret?.percent_ppa)} />
                <Metric label="Sacks returning" value={fmtPct(ret?.percent_sacks)} band={bandFromScore(ret?.percent_sacks)} />
              </div>
              <div className="metric-row" style={{ marginTop: "1rem" }}>
                <Metric label="Passing" value={fmtPct(ret?.percent_passing ?? ret?.percent_passing_ppa)} />
                <Metric label="Rushing" value={fmtPct(ret?.percent_rushing_ppa ?? ret?.percent_rushing)} />
                <Metric label="Receiving" value={fmtPct(ret?.percent_receiving_ppa ?? ret?.percent_receiving)} />
                <Metric label="Tackles" value={fmtPct(ret?.percent_tackles)} />
                <Metric label="TFL" value={fmtPct(ret?.percent_tfl)} />
                <Metric label="INT" value={fmtPct(ret?.percent_interceptions)} />
                <Metric label="Kicking" value={fmtPct(ret?.percent_kicking)} />
              </div>
            </div>
          </section>

          <section className="section">
            <h2>Transfer dependency and portal ledger</h2>
            <div className="split">
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Transfer dependency</h3>
                <div className="metric-row">
                  <Metric
                    label="Score"
                    value={`${fmtInt(dep?.transfer_dependency_score)} / 100`}
                    band={
                      Number(dep?.transfer_dependency_score) >= 70
                        ? "low"
                        : Number(dep?.transfer_dependency_score) >= 40
                          ? "mid"
                          : "high"
                    }
                  />
                  <Metric label="Usage from transfers" value={fmtPct(dep?.pct_usage_from_transfers)} />
                  <Metric label="Critical units" value={fmtInt(dep?.critical_units_on_transfers)} />
                </div>
              </div>
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Portal ledger</h3>
                <div className="ledger-grid">
                  <div className="ledger-cell">
                    <div className="label">Impact in</div>
                    <div className="value" style={{ color: "var(--ok)" }}>+{fmtInt(led?.impact_additions)}</div>
                  </div>
                  <div className="ledger-cell">
                    <div className="label">Impact out</div>
                    <div className="value" style={{ color: "var(--danger)" }}>−{fmtInt(led?.impact_losses)}</div>
                  </div>
                  <div className="ledger-cell">
                    <div className="label">Depth in</div>
                    <div className="value">+{fmtInt(led?.depth_additions)}</div>
                  </div>
                  <div className="ledger-cell">
                    <div className="label">Depth out</div>
                    <div className="value">−{fmtInt(led?.depth_losses)}</div>
                  </div>
                </div>
                <div className="metric-row" style={{ marginTop: "0.85rem" }}>
                  <Metric label="Net production" value={fmtNum(led?.net_production_gained)} />
                  <Metric label="Net talent" value={fmtNum(led?.net_talent_gained, 2)} />
                  <Metric
                    label="Projected starters"
                    value={`+${fmtInt(led?.projected_starters_added)} / −${fmtInt(led?.projected_starters_lost)}`}
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="section">
            <h2>Unit continuity grades</h2>
            <p className="lede">Worst continuity first — production, talent, and replacement risk by unit.</p>
            <div className="card-grid">
              {data.units.map((u) => (
                <div key={u.position_group} className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
                    <h3 style={{ margin: 0 }}>{unitLabel(u.position_group)}</h3>
                    <Pill tone={riskTone(u.replacement_risk)}>{u.replacement_risk}</Pill>
                  </div>
                  <div className="metric-row">
                    <Metric
                      label="Continuity"
                      value={fmtInt(u.continuity_score)}
                      band={bandFromScore(Number(u.continuity_score), true)}
                    />
                    <Metric label="Production returning" value={fmtPct(u.production_returning_pct)} band={bandFromScore(u.production_returning_pct)} />
                    <Metric label="Usage returning" value={fmtPct(u.usage_returning_pct)} band={bandFromScore(u.usage_returning_pct)} />
                  </div>
                  <p className="meta" style={{ marginTop: "0.65rem" }}>
                    Impact +{fmtInt(u.impact_additions)} / −{fmtInt(u.impact_losses)} · Net talent{" "}
                    {fmtNum(u.net_talent_gained, 2)}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {data.risks.length > 0 && (
            <section className="section">
              <h2>Replacement risk</h2>
              {data.risks.map((r, i) => (
                <div key={i} className={`alert ${r.replacement_risk === "elevated" ? "elevated" : ""}`}>
                  <div className="title">
                    {unitLabel(r.position_group)}{" "}
                    <Pill tone={riskTone(r.replacement_risk)}>{r.replacement_risk}</Pill>
                  </div>
                  <p>{r.callout}</p>
                </div>
              ))}
            </section>
          )}

          <section className="section">
            <h2>Portal moves</h2>
            <div className="split">
              <MoveList title="Arrivals" rows={arrivals} kind="in" />
              <MoveList title="Departures" rows={departures} kind="out" />
            </div>
          </section>

          <section className="section">
            <h2>QB room</h2>
            {data.roomClass && (
              <p className="lede">
                Room class: <Pill tone={qbTone(data.roomClass)}>{data.roomClass}</Pill>
              </p>
            )}
            <div className="card-grid">
              {data.qbs.map((q) => (
                <div key={`${q.first_name}-${q.last_name}`} className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                    <h3 style={{ margin: 0 }}>
                      {q.first_name} {q.last_name}
                    </h3>
                    <Pill tone={qbTone(q.qb_class)}>{q.qb_class}</Pill>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", margin: "0.5rem 0" }}>
                    {q.is_returning_starter && <Pill tone="trust">Returning starter</Pill>}
                    {q.is_backup && <Pill tone="muted">Backup</Pill>}
                    {q.is_transfer_addition && <Pill tone="amber">Transfer</Pill>}
                  </div>
                  <div className="metric-row">
                    <Metric label="Prior attempts" value={fmtInt(q.prior_pass_att)} />
                    <Metric label="Career attempts" value={fmtInt(q.career_pass_att)} />
                    <Metric label="Career PPA" value={fmtNum(q.career_avg_ppa_weighted, 3)} />
                    <Metric label="Turnover rate" value={fmtPct(q.turnover_rate)} />
                  </div>
                  <p className="meta" style={{ marginTop: "0.55rem" }}>
                    {[
                      q.stars != null ? `${fmtInt(q.stars)}★` : null,
                      q.transfer_count ? `${q.transfer_count} transfer(s)` : null,
                      q.last_transfer_origin ? `from ${q.last_transfer_origin}` : null,
                      q.career_rush_yds ? `${fmtInt(q.career_rush_yds)} career rush yds` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>
                </div>
              ))}
              {data.qbs.length === 0 && <div className="empty">No quarterbacks on the roster snapshot.</div>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function MoveList({
  title,
  rows,
  kind,
}: {
  title: string;
  rows: any[];
  kind: "in" | "out";
}) {
  const sorted = [...rows].sort((a, b) => {
    const ai = a.impact_class === "impact" ? 0 : 1;
    const bi = b.impact_class === "impact" ? 0 : 1;
    if (ai !== bi) return ai - bi;
    return Number(b.prior_production_score || 0) - Number(a.prior_production_score || 0);
  });
  return (
    <div>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {sorted.length === 0 && <p className="meta">None</p>}
      {sorted.map((m, i) => (
        <div key={i} className="card" style={{ marginBottom: "0.55rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.4rem" }}>
              <strong>
                {m.first_name} {m.last_name}
              </strong>
              <Pill tone="muted">{unitLabel(m.position_group)}</Pill>
            </div>
            <Pill tone={m.impact_class === "impact" ? (kind === "out" ? "danger" : "amber") : "muted"}>
              {m.impact_class}
            </Pill>
          </div>
          <p className="meta" style={{ margin: "0.35rem 0 0.65rem" }}>
            {kind === "in" ? `from ${m.origin || "—"}` : `to ${m.destination || "—"}`}
            {m.projected_starter ? " · Projected starter" : ""}
          </p>
          <div className="metric-row">
            <Metric label="Prior usage" value={fmtPct(m.prior_usage_overall)} />
            <Metric label="Prior production" value={fmtNum(m.prior_production_score)} />
            {m.transfer_stars != null && (
              <Metric label="Stars" value={`${fmtInt(m.transfer_stars)}★`} />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
