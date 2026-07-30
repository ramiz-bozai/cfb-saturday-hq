import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import PreviewOverview from "./pages/PreviewOverview";
import PreviewTeam from "./pages/PreviewTeam";
import SlatePage, { HomePage } from "./pages/Slate";
import { BriefPage, MatchupPage, ProjectionsPage } from "./pages/Other";

const DISCLAIMER_MARKET =
  "For analysis and entertainment only. Not gambling advice. Lines are public market context shown next to the model.";
const DISCLAIMER_CFP =
  "Playoff projections use Saturday HQ ratings plus published CFP structure. Not an official College Football Playoff selection.";

function defaultSeason() {
  const d = new Date();
  return d.getMonth() + 1 >= 8 ? d.getFullYear() : d.getFullYear() - 1;
}

export default function App() {
  const location = useLocation();
  const isPreview = location.pathname.startsWith("/preview");
  const [season, setSeason] = useState(defaultSeason());
  const [seasonType, setSeasonType] = useState("regular");
  const [week, setWeek] = useState(1);
  const [profiles, setProfiles] = useState<{ displayName: string; teams: string[] }[]>([]);
  const [profile, setProfile] = useState("");

  useEffect(() => {
    api<{ displayName: string; teams: string[] }[]>("/api/profiles")
      .then((rows) => {
        setProfiles(rows);
        if (rows[0]) setProfile(rows[0].displayName);
      })
      .catch(() => setProfiles([]));
  }, []);

  const myTeams = useMemo(() => {
    const p = profiles.find((x) => x.displayName === profile);
    return p?.teams || [];
  }, [profiles, profile]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="brand">Saturday HQ</h1>
          <p className="brand-sub">FBS college football intelligence</p>
        </div>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : undefined)}>
            Home
          </NavLink>
          <NavLink to="/slate" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Slate
          </NavLink>
          <NavLink to="/matchup" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Matchup
          </NavLink>
          <NavLink
            to="/projections"
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Projections
          </NavLink>
          <NavLink to="/brief" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Brief
          </NavLink>
          <NavLink
            to="/preview"
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Preview
          </NavLink>
        </nav>
      </header>

      {!isPreview && (
        <div className="controls">
          <div className="field">
            <label>Season</label>
            <input
              type="number"
              min={2015}
              max={2030}
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>Season type</label>
            <select value={seasonType} onChange={(e) => setSeasonType(e.target.value)}>
              <option value="regular">Regular</option>
              <option value="postseason">Postseason</option>
            </select>
          </div>
          <div className="field">
            <label>Week</label>
            <input
              type="number"
              min={0}
              max={16}
              value={week}
              onChange={(e) => setWeek(Number(e.target.value))}
            />
          </div>
        </div>
      )}

      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              myTeams={myTeams}
              profiles={profiles}
              profile={profile}
              setProfile={setProfile}
            />
          }
        />
        <Route
          path="/slate"
          element={
            <SlatePage
              season={season}
              seasonType={seasonType}
              week={week}
              myTeams={myTeams}
            />
          }
        />
        <Route
          path="/matchup"
          element={<MatchupPage season={season} seasonType={seasonType} week={week} />}
        />
        <Route path="/projections" element={<ProjectionsPage season={season} />} />
        <Route
          path="/brief"
          element={
            <BriefPage
              season={season}
              seasonType={seasonType}
              week={week}
              myTeams={myTeams}
            />
          }
        />
        <Route path="/preview" element={<PreviewOverview />} />
        <Route path="/preview/team" element={<PreviewTeam />} />
      </Routes>

      <footer className="disclaimer">
        <p>{DISCLAIMER_MARKET}</p>
        <p>{DISCLAIMER_CFP}</p>
      </footer>
    </div>
  );
}
