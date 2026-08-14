export function startColumnResize(
  event: React.PointerEvent,
  startWidth: number,
  onChange: (next: number) => void,
  min: number,
  max: number,
): void {
  event.preventDefault()
  const startX = event.clientX

  function handleMove(moveEvent: PointerEvent) {
    const next = Math.min(Math.max(startWidth + (moveEvent.clientX - startX), min), max)
    onChange(next)
  }
  function handleUp() {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', handleUp)
  }

  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', handleUp)
}

export function startRowResize(
  event: React.PointerEvent,
  startHeight: number,
  onChange: (next: number) => void,
  min: number,
  max: number,
): void {
  event.preventDefault()
  const startY = event.clientY

  function handleMove(moveEvent: PointerEvent) {
    const next = Math.min(Math.max(startHeight + (moveEvent.clientY - startY), min), max)
    onChange(next)
  }
  function handleUp() {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', handleUp)
  }

  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', handleUp)
}
