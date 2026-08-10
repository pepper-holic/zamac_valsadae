import { useEffect } from 'react'
import type { RefObject } from 'react'

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
}

// Space to play/pause, arrows to seek/navigate segments, Ctrl+Z / Ctrl+Shift+Z
// for undo/redo. Ignored while typing in an input/textarea so text editing
// isn't hijacked.
export function useKeyboardShortcuts(
  videoRef: RefObject<HTMLVideoElement | null>,
  handleUndo: () => void,
  handleRedo: () => void,
  handleNavigate: (direction: 'prev' | 'next') => void,
) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target)) return

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) {
          handleRedo()
        } else {
          handleUndo()
        }
        return
      }

      if (!videoRef.current) return

      if (event.code === 'Space') {
        event.preventDefault()
        if (videoRef.current.paused) videoRef.current.play()
        else videoRef.current.pause()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        videoRef.current.currentTime = Math.max(videoRef.current.currentTime - 1, 0)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        videoRef.current.currentTime = videoRef.current.currentTime + 1
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        handleNavigate('prev')
      } else if (event.key === 'ArrowDown') {
        event.preventDefault()
        handleNavigate('next')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [videoRef, handleNavigate, handleUndo, handleRedo])
}
