import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import {
  bandFromScore,
  continuityVerdict,
  dependencyBand,
  dependencyVerdict,
  fmtInt,
  fmtNum,
  fmtPct,
  netProductionVerdict,
  netTalentVerdict,
  qbTone,
  riskTone,
  unitLabel,
} from "../labels";
import { Metric, Pill } from "../components/ui";

type TeamData = {
  season: number;
  team: string;
  logoUrl: string | null;
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

/** Fixed board: offense row, then defense + ST. */
const UNIT_LAYOUT = ["QB", "RB", "WR/TE", "OL", "DL", "LB", "DB", "ST"] as const;
const SEASON_OPTIONS = [2026] as const;

const ROSTER_SOURCE_TIP = {
  constructed:
    "CFBD has not published this season’s roster yet. Built from the prior roster minus portal/draft exits plus portal arrivals.",
  published: "Official roster published by CFBD for this season.",
} as const;

export default function SeasonPreviewTeam() {
  const [params, setParams] = useSearchParams();
  const [teams, setTeams] = useState<string[]>([]);
  const [season, setSeason] = useState<number>(() => {
    const fromUrl = Number(params.get("season"));
    return SEASON_OPTIONS.includes(fromUrl as (typeof SEASON_OPTIONS)[number])
      ? fromUrl
      : SEASON_OPTIONS[0];
  });
  const [team, setTeam] = useState(params.get("team") || "");
  const [data, setData] = useState<TeamData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<string[]>(`/api/preview/teams?season=${season}`).then((list) => {
      setTeams(list);
      if (!team && list.length) setTeam(list.includes("Alabama") ? "Alabama" : list[0]);
    });
  }, [season]);

  useEffect(() => {
    if (!team) return;
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
  const unitByGroup = useMemo(() => {
    const map = new Map<string, any>();
    for (const u of data?.units || []) map.set(u.position_group, u);
    return map;
  }, [data]);

  const ret = data?.returning;
  const dep = data?.dependency;
  const led = data?.ledger;

  return (
    <div>
      <div className="controls">
        <div className="field">
          <label>Season</label>
          <select value={season} onChange={(e) => setSeason(Number(e.target.value))}>
            {SEASON_OPTIONS.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
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
            {data.logoUrl && (
              <img
                className="team-logo"
                src={data.logoUrl}
                alt=""
                width={72}
                height={72}
                loading="lazy"
              />
            )}
            <h1>{data.team}</h1>
            <Pill
              tone="muted"
              title={
                data.rosterSource === "published"
                  ? ROSTER_SOURCE_TIP.published
                  : ROSTER_SOURCE_TIP.constructed
              }
            >
              {data.rosterSource === "published" ? "Published roster" : "Constructed roster"}
            </Pill>
          </div>

          <section className="section">
            <h2>Prior production retained</h2>
            <p className="lede">
              Share of last season’s production still on the roster via non-transfers. Portal
              arrivals are under transfer dependency and the portal ledger.
            </p>
            <div className="card returning-card">
              <div className="returning-headline">
                <Metric label="Offense retained" value={fmtPct(ret?.percent_offense_returning)} band={bandFromScore(ret?.percent_offense_returning)} />
                <Metric label="Defense retained" value={fmtPct(ret?.percent_defense_returning)} band={bandFromScore(ret?.percent_defense_returning)} />
                <Metric label="PPA retained" value={fmtPct(ret?.percent_ppa)} band={bandFromScore(ret?.percent_ppa)} />
                <Metric label="Sacks retained" value={fmtPct(ret?.percent_sacks)} band={bandFromScore(ret?.percent_sacks)} />
              </div>
              <div className="returning-groups">
                <div className="returning-group">
                  <p className="group-label">Offense</p>
                  <div className="returning-detail">
                    <Metric label="Passing" value={fmtPct(ret?.percent_passing ?? ret?.percent_passing_ppa)} />
                    <Metric label="Rushing" value={fmtPct(ret?.percent_rushing_ppa ?? ret?.percent_rushing)} />
                    <Metric label="Receiving" value={fmtPct(ret?.percent_receiving_ppa ?? ret?.percent_receiving)} />
                  </div>
                </div>
                <div className="returning-group">
                  <p className="group-label">Defense</p>
                  <div className="returning-detail">
                    <Metric label="Tackles" value={fmtPct(ret?.percent_tackles)} />
                    <Metric label="TFL" value={fmtPct(ret?.percent_tfl)} />
                    <Metric label="INT" value={fmtPct(ret?.percent_interceptions)} />
                  </div>
                </div>
                <div className="returning-group">
                  <p className="group-label">Special teams</p>
                  <div className="returning-detail">
                    <Metric label="Kicking" value={fmtPct(ret?.percent_kicking)} />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="section">
            <h2>Transfer dependency and portal ledger</h2>
            <p className="lede">
              <span>Same score overall, then split by side.</span>
              <span>Defense usage is share of team tackle-weighted production (not CFBD snaps).</span>
            </p>
            <div className="split">
              <div className="card">
                <h3 style={{ marginTop: 0 }}>Transfer dependency</h3>
                <div className="metric-row">
                  <Metric
                    label="Overall"
                    verdict={dependencyVerdict(dep?.transfer_dependency_score)}
                    value={`${fmtInt(dep?.transfer_dependency_score)} / 100`}
                    band={dependencyBand(dep?.transfer_dependency_score)}
                    hint="How much of last year’s usage now rides on portal arrivals."
                  />
                  <Metric
                    label="Usage from transfers"
                    value={fmtPct(dep?.pct_usage_from_transfers)}
                  />
                  <Metric
                    label="Critical units"
                    value={fmtInt(dep?.critical_units_on_transfers)}
                  />
                </div>
                <p className="lede" style={{ marginBottom: "0.35rem", marginTop: "1rem" }}>
                  Offense (QB, RB, WR/TE, OL)
                </p>
                <div className="metric-row">
                  <Metric
                    label="Dependency"
                    verdict={dependencyVerdict(dep?.offense_transfer_dependency_score)}
                    value={`${fmtInt(dep?.offense_transfer_dependency_score)} / 100`}
                    band={dependencyBand(dep?.offense_transfer_dependency_score)}
                  />
                  <Metric
                    label="Usage from transfers"
                    value={fmtPct(dep?.offense_pct_usage_from_transfers)}
                  />
                  <Metric
                    label="Critical units"
                    value={fmtInt(dep?.offense_critical_units_on_transfers)}
                  />
                </div>
                <p className="lede" style={{ marginBottom: "0.35rem", marginTop: "1rem" }}>
                  Defense (DL, LB, Secondary)
                </p>
                <div className="metric-row">
                  <Metric
                    label="Dependency"
                    verdict={dependencyVerdict(dep?.defense_transfer_dependency_score)}
                    value={`${fmtInt(dep?.defense_transfer_dependency_score)} / 100`}
                    band={dependencyBand(dep?.defense_transfer_dependency_score)}
                  />
                  <Metric
                    label="Usage from transfers"
                    value={fmtPct(dep?.defense_pct_usage_from_transfers)}
                  />
                  <Metric
                    label="Critical units"
                    value={fmtInt(dep?.defense_critical_units_on_transfers)}
                  />
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
                <div className="metric-row ledger-metrics">
                  <Metric
                    label="Off net"
                    verdict={netProductionVerdict(led?.net_offense_production_gained).verdict}
                    value={fmtNum(led?.net_offense_production_gained)}
                    band={netProductionVerdict(led?.net_offense_production_gained).band}
                    hint="Prior offense production (PPA-based) gained minus lost via portal/draft."
                  />
                  <Metric
                    label="Def net"
                    verdict={netProductionVerdict(led?.net_defense_production_gained).verdict}
                    value={fmtNum(led?.net_defense_production_gained)}
                    band={netProductionVerdict(led?.net_defense_production_gained).band}
                    hint="Prior defense production (tackle-weighted) gained minus lost via portal/draft."
                  />
                  <Metric
                    label="Net talent"
                    verdict={netTalentVerdict(led?.net_talent_gained).verdict}
                    value={fmtNum(led?.net_talent_gained, 2)}
                    band={netTalentVerdict(led?.net_talent_gained).band}
                    hint="Avg recruiting quality of arrivals minus departures."
                  />
                  <Metric
                    label="Projected starters"
                    value={`+${fmtInt(led?.projected_starters_added)} / −${fmtInt(led?.projected_starters_lost)}`}
                    hint="High-usage players added vs departed."
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="section">
            <h2>Unit continuity grades</h2>
            <p className="lede">
              <span>Continuity (0–100) is how much prior production and usage is still on the roster at that unit.</span>
              <span>Offense: CFBD PPA/usage.</span>
              <span>Defense (DL/LB/DB): tackle-weighted production and share of team defense production.</span>
              <span>OL/ST: roster retention when no usage exists.</span>
            </p>
            <div className="unit-grid">
              {UNIT_LAYOUT.map((pg) => {
                const u = unitByGroup.get(pg);
                if (!u) {
                  return (
                    <div key={pg} className="card unit-empty">
                      <span className="meta">{unitLabel(pg)} · no data</span>
                    </div>
                  );
                }
                return (
                  <div key={pg} className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
                      <h3 style={{ margin: 0 }}>{unitLabel(pg)}</h3>
                      <Pill tone={riskTone(u.replacement_risk)}>{u.replacement_risk}</Pill>
                    </div>
                    <div className="metric-row">
                      <Metric
                        label="Continuity"
                        verdict={continuityVerdict(u.continuity_score, true)}
                        value={`${fmtInt(u.continuity_score)} / 100`}
                        band={bandFromScore(Number(u.continuity_score), true)}
                      />
                      <Metric
                        label="Production returning"
                        value={fmtPct(u.production_returning_pct)}
                        band={bandFromScore(u.production_returning_pct)}
                      />
                      <Metric
                        label="Usage returning"
                        value={fmtPct(u.usage_returning_pct)}
                        band={bandFromScore(u.usage_returning_pct)}
                      />
                    </div>
                    <p className="meta" style={{ marginTop: "0.65rem" }}>
                      Impact +{fmtInt(u.impact_additions)} / −{fmtInt(u.impact_losses)} · Net talent{" "}
                      {fmtNum(u.net_talent_gained, 2)}
                    </p>
                  </div>
                );
              })}
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
            <div className="explainer">
              <p>How to read prior production and usage on each move.</p>
              <dl>
                <div>
                  <dt>Production</dt>
                  <dd>
                    <span>Offense: total PPA, or usage × 50.</span>
                    <span>Defense (DL/LB/DB): tackles + 2×(TFL − sacks) + 3×sacks + 2×INT.</span>
                  </dd>
                </div>
                <div>
                  <dt>Usage</dt>
                  <dd>
                    <span>Offense: CFBD play share.</span>
                    <span>Defense: share of that team’s defensive production (not snap %).</span>
                  </dd>
                </div>
                <div>
                  <dt>Scale</dt>
                  <dd>
                    <span>~0 little role · ~10–40 solid · ~15+ often impact · 100+ star season</span>
                  </dd>
                </div>
              </dl>
            </div>
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
