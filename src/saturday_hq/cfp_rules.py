"""Published 2026 CFP structure helpers.

Sources:
- https://collegefootballplayoff.com/sports/2024/5/29/12-team-format.aspx
- https://www.ncaa.com/news/football/article/2026-02-03/how-college-football-playoff-automatic-qualifiers-work-byes-seeds
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from saturday_hq.config import G6_CANONICAL, POWER4_CANONICAL


CFP_RULES_TEXT = """
# College Football Playoff rules used by Saturday HQ (2026 season)

Primary sources:
- CFP 12-team format page
- NCAA explainers on automatic qualifiers (updated for 2026)

## Field
- 12 teams

## Automatic qualifiers (2026)
1. ACC champion
2. Big Ten champion
3. Big 12 champion
4. SEC champion
5. Highest-ranked team from Group of 6 conferences
   (American, CUSA, MAC, Mountain West, Pac-12, Sun Belt).
   This team does NOT have to be a conference champion.
6. Notre Dame if ranked in the final top 12

## At-large
- Fill remaining slots with the next highest-ranked teams until 12 are selected.

## Seeding and byes
- Seeds follow final ranking order used by the simulator (committee stand-in).
- Seeds 1-4 receive a first-round bye.
- First round: 12@5, 11@6, 10@7, 9@8.
- If an automatic qualifier falls outside the top 12, they remain in the field
  and are seeded at the bottom of the 12-team pool.

## Committee criteria (documentation only — do not invent in Genie)
Performance on the field, conference championships, strength of schedule,
head-to-head results, and results against common opponents.

## Saturday HQ limitation
The simulator substitutes Saturday HQ model/preseason ratings for the official
selection committee ranking. Always display the CFP disclaimer.
""".strip()


@dataclass
class TeamSeedInput:
    team: str
    rank: int
    conference: str
    is_conference_champion: bool = False
    is_notre_dame: bool = False


@dataclass
class PlayoffBid:
    team: str
    rank: int
    conference: str
    bid_type: str  # power4_aq | g6_aq | notre_dame_aq | at_large
    seed: Optional[int] = None


def _is_power4(conference: str) -> bool:
    return conference in POWER4_CANONICAL


def _is_g6(conference: str) -> bool:
    return conference in G6_CANONICAL


def select_playoff_field(teams: Iterable[TeamSeedInput]) -> List[PlayoffBid]:
    """Apply published 2026 AQ structure using an external ranking stand-in.

    `teams` must already be sorted by ascending rank (1 = best).
    """
    ordered = sorted(list(teams), key=lambda t: t.rank)
    selected: Dict[str, PlayoffBid] = {}

    # Power 4 conference champions are automatic, regardless of rank.
    for conf in sorted(POWER4_CANONICAL):
        champs = [
            t
            for t in ordered
            if t.is_conference_champion and t.conference == conf
        ]
        if not champs:
            continue
        champ = champs[0]
        selected[champ.team] = PlayoffBid(
            team=champ.team,
            rank=champ.rank,
            conference=champ.conference,
            bid_type="power4_aq",
        )

    # Highest-ranked G6 team (champion not required).
    g6_candidates = [t for t in ordered if _is_g6(t.conference)]
    if g6_candidates:
        g6 = g6_candidates[0]
        if g6.team not in selected:
            selected[g6.team] = PlayoffBid(
                team=g6.team,
                rank=g6.rank,
                conference=g6.conference,
                bid_type="g6_aq",
            )

    # Notre Dame AQ if ranked top 12.
    for t in ordered:
        if t.is_notre_dame and t.rank <= 12 and t.team not in selected:
            selected[t.team] = PlayoffBid(
                team=t.team,
                rank=t.rank,
                conference=t.conference,
                bid_type="notre_dame_aq",
            )
            break

    # At-large fill to 12.
    for t in ordered:
        if len(selected) >= 12:
            break
        if t.team in selected:
            continue
        selected[t.team] = PlayoffBid(
            team=t.team,
            rank=t.rank,
            conference=t.conference,
            bid_type="at_large",
        )

    field = list(selected.values())

    # Seeding: by rank ascending. AQs outside top 12 go to bottom of pool,
    # preserving relative order among those demoted teams.
    in_top12 = [b for b in field if b.rank <= 12]
    outside = [b for b in field if b.rank > 12]
    in_top12.sort(key=lambda b: b.rank)
    outside.sort(key=lambda b: b.rank)
    seeded = in_top12 + outside
    for i, bid in enumerate(seeded, start=1):
        bid.seed = i
    return seeded


FIRST_ROUND_PAIRINGS = ((12, 5), (11, 6), (10, 7), (9, 8))
BYE_SEEDS = (1, 2, 3, 4)
