type Props = {
  isPlaying: boolean
  playbackRate: number
  loopSegment: boolean
  onTogglePlay: () => void
  onStep: (deltaSeconds: number) => void
  onRateChange: (rate: number) => void
  onLoopToggle: () => void
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]
const STEP_SECONDS = 1

export function TransportControls({
  isPlaying,
  playbackRate,
  loopSegment,
  onTogglePlay,
  onStep,
  onRateChange,
  onLoopToggle,
}: Props) {
  return (
    <div className="transport-controls">
      <button type="button" onClick={() => onStep(-STEP_SECONDS)} data-tip="1초 뒤로 이동 (단축키: ←)">
        ◀◀ 1s
      </button>
      <button type="button" className="play-button" onClick={onTogglePlay} data-tip="재생/일시정지 (단축키: Space)">
        {isPlaying ? '일시정지' : '재생'}
      </button>
      <button type="button" onClick={() => onStep(STEP_SECONDS)} data-tip="1초 앞으로 이동 (단축키: →)">
        1s ▶▶
      </button>

      <label className="rate-select" data-tip="재생 속도를 조절합니다.">
        속도
        <select value={playbackRate} onChange={(event) => onRateChange(Number(event.target.value))}>
          {PLAYBACK_RATES.map((rate) => (
            <option key={rate} value={rate}>
              {rate}x
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox-label" data-tip="켜두면 선택한 문장의 시작~종료 구간을 자동으로 반복 재생합니다.">
        <input type="checkbox" checked={loopSegment} onChange={onLoopToggle} />
        현재 구간 반복
      </label>
    </div>
  )
}
