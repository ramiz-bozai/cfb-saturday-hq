/**
 * Source attribution for Season Preview tooltips.
 * Recruiting / portal talent: 247Sports ratings republished by CollegeFootballData (CFBD).
 * Usage / production / PPA: CFBD game stats.
 */

export const SOURCE = {
  hsStars: "247Sports star rating from CollegeFootballData.",
  hsRating: "247Sports composite rating (0-1) from CollegeFootballData.",
  hsClass:
    "Avg 247Sports stars from CollegeFootballData. National rank uses avg 247Sports composite rating (min 10 rated).",
  transferStars: "247Sports transfer star rating from CollegeFootballData.",
  talentScore:
    "247Sports talent from CollegeFootballData: transfer rating, else HS recruiting rating, else stars÷5. Used for OL/ST when usage/PPA isn’t available.",
  netTalent:
    "Portal only: avg 247Sports talent in minus avg out (CollegeFootballData transfer rating / stars÷5) - not the HS class.",
  continuity:
    "0-100 blend of returning CollegeFootballData usage/production (or headcount for OL/ST).",
  qbStars: "247Sports HS recruiting stars from CollegeFootballData, on the roster snapshot.",
  offNet:
    "Prior offense production (CollegeFootballData PPA for QB/RB/WR) gained minus lost via portal/draft. OL is on net talent.",
  defNet:
    "Prior defense production (CollegeFootballData tackle-weighted index) gained minus lost via portal/draft.",
} as const;
