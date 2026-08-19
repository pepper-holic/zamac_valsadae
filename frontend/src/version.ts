// Single source of truth for the app's own version number as far as the
// frontend is concerned. Bump this by hand alongside `installer/installer.iss`'s
// MyAppVersion and CHANGELOG.md on every release - there is no build-time
// codegen syncing these, so it's a manual checklist item (see
// docs/ARCHITECTURE.md's deploy section).
export const APP_VERSION = '1.0.0'
