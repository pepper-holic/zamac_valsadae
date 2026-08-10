import type { MediaItem, Project } from '../api/types'

export function projectLabel(project: Project): string {
  if (project.name) return project.name
  if (project.items[0]) return project.items[0].filename
  return '(이름 없는 프로젝트)'
}

export function updateItemInProject(
  project: Project,
  itemId: string,
  updater: (item: MediaItem) => MediaItem,
): Project {
  return { ...project, items: project.items.map((i) => (i.id === itemId ? updater(i) : i)) }
}
