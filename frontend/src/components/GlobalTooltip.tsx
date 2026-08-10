import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

type TooltipState = {
  text: string
  x: number
  placement: 'top' | 'bottom'
  y: number
}

const GAP = 9
const MIN_SPACE_ABOVE = 60

/**
 * Renders data-tip bubbles into document.body with position: fixed, computed
 * from the hovered element's real screen position - immune to clipping by any
 * ancestor's overflow:hidden/auto, unlike the old pure-CSS ::after/::before
 * approach (which broke for [data-tip] elements anywhere near the top edge
 * of a scrolling panel: toolbar, panel headings, video aspect-ratio picker,
 * etc - anywhere close enough to a container edge that the upward-opening
 * bubble had nowhere to render).
 *
 * Mounted once at the app root; every [data-tip] element elsewhere in the
 * tree needs no changes - this listens globally via event delegation.
 */
export function GlobalTooltip() {
  const [state, setState] = useState<TooltipState | null>(null)

  useEffect(() => {
    function targetOf(event: Event): HTMLElement | null {
      const node = event.target
      if (!(node instanceof Element)) return null
      return node.closest<HTMLElement>('[data-tip]')
    }

    function show(event: Event) {
      const el = targetOf(event)
      const text = el?.getAttribute('data-tip')
      if (!el || !text) return
      const rect = el.getBoundingClientRect()
      const placement: 'top' | 'bottom' = rect.top > MIN_SPACE_ABOVE ? 'top' : 'bottom'
      setState({
        text,
        x: Math.min(Math.max(rect.left + rect.width / 2, 90), window.innerWidth - 90),
        y: placement === 'top' ? rect.top - GAP : rect.bottom + GAP,
        placement,
      })
    }

    function hide(event: Event) {
      const el = targetOf(event)
      if (el) setState(null)
    }

    document.addEventListener('mouseover', show, true)
    document.addEventListener('mouseout', hide, true)
    document.addEventListener('focusin', show, true)
    document.addEventListener('focusout', hide, true)
    return () => {
      document.removeEventListener('mouseover', show, true)
      document.removeEventListener('mouseout', hide, true)
      document.removeEventListener('focusin', show, true)
      document.removeEventListener('focusout', hide, true)
    }
  }, [])

  if (!state) return null

  return createPortal(
    <div
      className={`global-tooltip global-tooltip-${state.placement}`}
      style={{ left: state.x, top: state.y }}
      role="tooltip"
    >
      {state.text}
    </div>,
    document.body,
  )
}
