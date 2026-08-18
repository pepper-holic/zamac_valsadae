import { useEffect, useRef } from 'react'

export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    const items = Array.from(node.querySelectorAll<HTMLElement>('[data-reveal]'))
    if (items.length === 0) return

    const reveal = (el: HTMLElement) => el.classList.add('is-visible')

    if (typeof IntersectionObserver === 'undefined') {
      items.forEach(reveal)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            reveal(entry.target as HTMLElement)
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0, rootMargin: '0px 0px -10% 0px' },
    )
    items.forEach((item) => observer.observe(item))

    // Safety net: some browser automation / preview environments never fire
    // the IntersectionObserver callback for already-on-screen elements.
    const fallback = window.setTimeout(() => items.forEach(reveal), 700)

    return () => {
      observer.disconnect()
      window.clearTimeout(fallback)
    }
  }, [])

  return ref
}
