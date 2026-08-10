type Props = {
  tip: string
}

/** Small "ⓘ" affordance next to a panel heading - hover/focus shows a guide bubble
 * explaining what that panel does, via the shared [data-tip] tooltip system. */
export function PanelHint({ tip }: Props) {
  return (
    <span className="panel-hint" data-tip={tip} tabIndex={0} aria-label="이 화면 설명">
      ⓘ
    </span>
  )
}
