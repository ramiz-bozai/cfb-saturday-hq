import { useEffect, useState } from "react";
import { api } from "../api";

type BriefResponse = {
  status: "ready" | "pending" | "missing";
  text: string | null;
  error?: string;
};

export default function TeamGenieBrief({
  team,
  season,
}: {
  team: string;
  season: number;
}) {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setBrief(null);
    setError(null);
    api<BriefResponse>(
      `/api/genie/brief?team=${encodeURIComponent(team)}&season=${season}`
    )
      .then((data) => {
        if (!cancelled) setBrief(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Brief unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [team, season]);

  if (error) {
    return (
      <div className="card genie-brief">
        <p className="meta" style={{ margin: 0 }}>
          Genie brief unavailable.
        </p>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="card genie-brief">
        <p className="meta" style={{ margin: 0 }}>
          Loading Genie brief…
        </p>
      </div>
    );
  }

  if (brief.status !== "ready" || !brief.text) {
    return (
      <div className="card genie-brief">
        <p className="meta" style={{ margin: 0 }}>
          Genie brief not ready yet. Run{" "}
          <code>node scripts/warm_genie_briefs.js --team={team}</code> to generate.
        </p>
      </div>
    );
  }

  return (
    <div className="card genie-brief">
      <div className="genie-brief-label">Genie bottom line</div>
      <p className="genie-brief-text">{brief.text}</p>
    </div>
  );
}
