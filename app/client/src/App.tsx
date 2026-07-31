import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import BrandLogo from "./components/BrandLogo";
import SeasonPreviewOverview from "./pages/SeasonPreviewOverview";
import SeasonPreviewTeam from "./pages/SeasonPreviewTeam";
import { HomePage } from "./pages/Slate";

const DISCLAIMER_MARKET =
  "For analysis and entertainment only. Not gambling advice. Lines are public market context shown next to the model.";
const DISCLAIMER_CFP =
  "Playoff projections use Saturday HQ ratings plus published CFP structure. Not an official College Football Playoff selection.";

export default function App() {
  const location = useLocation();
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
        <div className="brand-block">
          <BrandLogo />
          <p className="brand-powered">
            Powered by the <span>Databricks Data + AI Platform</span>
          </p>
        </div>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : undefined)}>
            Home
          </NavLink>
          <NavLink
            to="/season-preview"
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            Season Preview
          </NavLink>
        </nav>
      </header>

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
        <Route path="/slate" element={<Navigate to="/" replace />} />
        <Route path="/matchup" element={<Navigate to="/" replace />} />
        <Route path="/projections" element={<Navigate to="/" replace />} />
        <Route path="/brief" element={<Navigate to="/" replace />} />
        <Route path="/season-preview" element={<SeasonPreviewOverview />} />
        <Route path="/season-preview/team" element={<SeasonPreviewTeam />} />
        <Route path="/preview" element={<Navigate to="/season-preview" replace />} />
        <Route
          path="/preview/team"
          element={<Navigate to={`/season-preview/team${location.search}`} replace />}
        />
      </Routes>

      <footer className="disclaimer">
        <p>{DISCLAIMER_MARKET}</p>
        <p>{DISCLAIMER_CFP}</p>
        <p>
          Data from{" "}
          <a href="https://collegefootballdata.com" target="_blank" rel="noreferrer">
            CFBD (College Football Data.com)
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
