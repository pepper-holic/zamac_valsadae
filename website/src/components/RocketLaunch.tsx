import './rocket-launch.css'

const STARS = [
  { x: 10, y: 10, r: 1.4 },
  { x: 90, y: 8, r: 1.1 },
  { x: 92, y: 46, r: 1.2 },
  { x: 8, y: 50, r: 1 },
]

export function RocketLaunch() {
  return (
    <svg
      className="rocket-launch"
      viewBox="0 0 100 100"
      role="img"
      aria-label="자막을 연료 삼아 발사되는 로켓 일러스트"
    >
      {STARS.map((star, i) => (
        <circle key={i} className="rocket-star" cx={star.x} cy={star.y} r={star.r} />
      ))}

      <g className="rocket-body-group">
        {/* flat-bottomed capsule: dome top, straight sides, flat base for fins to attach to */}
        <path className="rocket-hull" d="M 32 32 A 18 18 0 0 1 68 32 L 68 68 L 32 68 Z" />

        <polygon className="rocket-fin" points="32,48 14,68 32,62" />
        <polygon className="rocket-fin" points="68,48 86,68 68,62" />

        <circle className="rocket-window" cx="50" cy="32" r="8" />
        <circle className="rocket-window-dot" cx="50" cy="32" r="2.5" />

        <polygon className="rocket-flame" points="42,68 58,68 50,86" />
      </g>
    </svg>
  )
}
