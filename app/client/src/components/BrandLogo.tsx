import { Link } from "react-router-dom";

/** Saturday HQ mark - football crest + wordmark lockup */
export default function BrandLogo() {
  return (
    <Link to="/" className="brand-lockup" aria-label="Saturday HQ home">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 64 64" className="brand-mark-svg">
          <defs>
            <linearGradient id="shField" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#126048" />
              <stop offset="100%" stopColor="#072820" />
            </linearGradient>
            <linearGradient id="shBall" x1="15%" y1="0%" x2="85%" y2="100%">
              <stop offset="0%" stopColor="#faf6ee" />
              <stop offset="55%" stopColor="#e8e0d0" />
              <stop offset="100%" stopColor="#cfc5b0" />
            </linearGradient>
          </defs>

          <circle cx="32" cy="32" r="30" fill="url(#shField)" />
          <circle
            cx="32"
            cy="32"
            r="30"
            fill="none"
            stroke="rgba(242,240,233,0.28)"
            strokeWidth="1.5"
          />

          {/* Yard hash hints */}
          <g stroke="rgba(242,240,233,0.16)" strokeWidth="1">
            <line x1="16" y1="20" x2="48" y2="20" />
            <line x1="13" y1="32" x2="51" y2="32" />
            <line x1="16" y1="44" x2="48" y2="44" />
          </g>

          {/* Goal posts */}
          <g stroke="#c45c26" strokeWidth="1.7" strokeLinecap="round" fill="none">
            <path d="M32 7.5 V13.5" />
            <path d="M26.5 13.5 H37.5" />
            <path d="M26.5 13.5 V17" />
            <path d="M37.5 13.5 V17" />
          </g>

          {/* Football + laces as one rotated group */}
          <g transform="rotate(-34 32 32)">
            <ellipse
              cx="32"
              cy="32"
              rx="19"
              ry="11.8"
              fill="url(#shBall)"
              stroke="#14201a"
              strokeWidth="1.25"
            />
            <path
              d="M15 32 H49"
              fill="none"
              stroke="#14201a"
              strokeWidth="1.3"
              strokeLinecap="round"
            />
            <g stroke="#c45c26" strokeWidth="1.55" strokeLinecap="round">
              <line x1="28.5" y1="28.2" x2="35.5" y2="35.8" />
              <line x1="26.8" y1="30.6" x2="30.2" y2="27.4" />
              <line x1="28.6" y1="32.6" x2="32" y2="29.4" />
              <line x1="30.4" y1="34.6" x2="33.8" y2="31.4" />
              <line x1="32.2" y1="36.6" x2="35.6" y2="33.4" />
            </g>
          </g>
        </svg>
      </span>
      <span className="brand-copy">
        <h1 className="brand">
          Saturday <span className="brand-hq">HQ</span>
        </h1>
        <span className="brand-sub">FBS College Football Intelligence</span>
      </span>
    </Link>
  );
}
