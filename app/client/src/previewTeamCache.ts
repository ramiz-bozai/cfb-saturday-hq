import { api } from "./api";

type TeamData = Record<string, unknown> & { team?: string; season?: number };

const cache = new Map<string, TeamData>();
const inflight = new Map<string, Promise<TeamData>>();

function key(season: number, team: string) {
  return `v4::${season}::${team}`;
}

export function getCachedPreviewTeam(season: number, team: string): TeamData | undefined {
  return cache.get(key(season, team));
}

export function setCachedPreviewTeam(season: number, team: string, data: TeamData) {
  cache.set(key(season, team), data);
}

/** Fetch a team payload, using the in-memory client cache when possible. */
export function fetchPreviewTeam(season: number, team: string): Promise<TeamData> {
  const k = key(season, team);
  const hit = cache.get(k);
  // Stale payloads from before hsRecruits must not short-circuit the network.
  if (hit && Array.isArray(hit.hsRecruits)) return Promise.resolve(hit);

  const pending = inflight.get(k);
  if (pending) return pending;

  const req = api<TeamData>(`/api/preview/team/${encodeURIComponent(team)}?season=${season}`)
    .then((data) => {
      cache.set(k, data);
      inflight.delete(k);
      return data;
    })
    .catch((err) => {
      inflight.delete(k);
      throw err;
    });
  inflight.set(k, req);
  return req;
}

/** Prefetch several teams with limited concurrency (fire-and-forget safe). */
export function prefetchPreviewTeams(
  season: number,
  teams: string[],
  concurrency = 3
): Promise<void> {
  const unique = [...new Set(teams.filter(Boolean))];
  const missing = unique.filter((t) => !cache.has(key(season, t)) && !inflight.has(key(season, t)));
  if (!missing.length) return Promise.resolve();

  let i = 0;
  async function worker() {
    while (i < missing.length) {
      const idx = i++;
      try {
        await fetchPreviewTeam(season, missing[idx]);
      } catch {
        // Prefetch is best-effort.
      }
    }
  }
  return Promise.all(
    Array.from({ length: Math.min(concurrency, missing.length) }, () => worker())
  ).then(() => undefined);
}
