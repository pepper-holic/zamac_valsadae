import { useLayoutEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Align = 'left' | 'right'

type Position = { top: number; left?: number; right?: number }

type Props = {
  anchorRef: React.RefObject<HTMLElement | null>
  open: boolean
  align?: Align
  className: string
  children: ReactNode
}

const GAP = 4

/**
 * Renders dropdown content into document.body with position: fixed, computed
 * from the trigger's real screen position - immune to clipping by the
 * toolbar's own overflow-x:auto/overflow-y:hidden (needed to keep the
 * toolbar from wrapping to a second line), unlike a plain position:absolute
 * child which gets clipped to the toolbar's box. Same rationale as
 * GlobalTooltip.
 */
export function ToolbarDropdown({ anchorRef, open, align = 'left', className, children }: Props) {
  const [pos, setPos] = useState<Position | null>(null)

  useLayoutEffect(() => {
    if (!open) return
    const anchor = anchorRef.current
    if (!anchor) return

    function updatePosition() {
      const rect = anchor!.getBoundingClientRect()
      setPos(
        align === 'right'
          ? { top: rect.bottom + GAP, right: window.innerWidth - rect.right }
          : { top: rect.bottom + GAP, left: rect.left },
      )
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, anchorRef, align])

  if (!open || !pos) return null

  return createPortal(
    <div
      className={className}
      style={{ position: 'fixed', top: pos.top, left: pos.left, right: pos.right }}
      role="menu"
      data-toolbar-portal
    >
      {children}
    </div>,
    document.body,
  )
}
