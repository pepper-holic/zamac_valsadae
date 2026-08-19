import { expect, test } from '@playwright/test'
import type { MediaItem, Project, Segment, SubtitleStyle } from '../src/api/types'

// Smoke test only: verifies the screens are actually wired together
// (upload -> item appears -> segment list renders -> export triggers a
// download) using a mocked backend, not that real transcription/rendering
// works. A full E2E through actual Whisper/ffmpeg would need multi-GB model
// downloads and minutes of processing per run - too heavy/slow for this to
// stay a "does the wiring still work" check. To skip simulating the
// transcribe polling loop (see useProjectWorkspace.ts), the mocked upload
// response below returns an item that's already "transcribed" with a
// segment, as if transcription had just finished.

const DEFAULT_STYLE: SubtitleStyle = {
  font_family: 'Pretendard',
  font_size: 32,
  font_weight: 'bold',
  color: '#FFFFFF',
  outline_color: '#000000',
  outline_width: 2,
  background: null,
  position: 'bottom',
  fade_in_ms: 0,
  fade_out_ms: 0,
  karaoke_highlight: false,
  auto_line_break: false,
  max_line_chars: 42,
}

function makeSegment(): Segment {
  return {
    id: 'segment-1',
    start: 0,
    end: 2,
    text: '안녕하세요',
    speaker: null,
    translation: 'Hello',
    transcription_quality: 'good',
    transcription_quality_reason: null,
    translation_quality: 'good',
    translation_quality_reason: null,
    readability_flag: null,
    readability_reason: null,
    reviewed: false,
    words: [],
  }
}

function makeItem(): MediaItem {
  return {
    id: 'item-1',
    filename: 'sample.mp4',
    media_path: '/tmp/sample.mp4',
    status: 'transcribed',
    whisper_model: 'small',
    error: null,
    progress: null,
    stage: null,
    started_at: null,
    segments: [makeSegment()],
    rendered_path: null,
  }
}

function makeProject(items: MediaItem[] = []): Project {
  return {
    id: 'project-1',
    name: '테스트 프로젝트',
    items,
    glossary: {},
    subtitle_style: DEFAULT_STYLE,
    style_presets: [],
  }
}

test('upload -> segment list -> export is wired end to end', async ({ page }) => {
  // Marketing-site update check (useUpdateCheck) - real internet call in
  // prod, must not hit the network in a test.
  await page.route('https://site.168-110-107-78.nip.io/**', (route) =>
    route.fulfill({ status: 404, body: '' }),
  )
  // VideoStage's <video src> - we don't need real media, just something
  // that doesn't error the page.
  await page.route('**/media', (route) => route.fulfill({ status: 200, body: '' }))

  await page.route('**/projects', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: [] })
    } else if (route.request().method() === 'POST') {
      await route.fulfill({ json: makeProject() })
    } else {
      await route.continue()
    }
  })

  await page.route('**/projects/*/items', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    await route.fulfill({ json: makeItem() })
  })

  await page.route('**/export*', async (route) => {
    await route.fulfill({ status: 200, body: '1\n00:00:00,000 --> 00:00:02,000\n안녕하세요\n' })
  })

  await page.goto('/')

  await expect(page.getByRole('heading', { name: '자막발사대' })).toBeVisible()

  const uploadInput = page.getByLabel('+ 영상/오디오 업로드')
  await uploadInput.setInputFiles({
    name: 'sample.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('fake video content'),
  })

  // Uploaded item's filename should now show up in the file-picker dropdown,
  // proving the upload response was merged into state. It's an <option>
  // inside a closed <select>, so assert its presence rather than visibility.
  await expect(page.locator('option', { hasText: 'sample.mp4' })).toHaveCount(1)

  // The mocked item already has a segment - the segment list should render
  // its text without any further action.
  await expect(page.getByText('안녕하세요').first()).toBeVisible()

  await page.getByRole('button', { name: /내보내기/ }).click()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '선택 항목 다운로드' }).click()
  const download = await downloadPromise

  expect(download.url()).toContain('/projects/project-1/items/item-1/export')
})
