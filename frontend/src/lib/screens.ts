import type { Role, ScreenKey } from '@/types/api'

// Mirrors backend screens.py's SCREENS/ROLE_SCREENS -- kept in sync manually
// since both are small, fixed, rarely-changed constants (not worth a
// dedicated API round-trip just to fetch a 9-entry list).
export const SCREEN_LABELS: Record<ScreenKey, string> = {
  dashboard: 'Dashboard',
  reports: 'Raporlar',
  monitoring: 'Monitoring',
  logs: 'Loglar',
  emails: 'E-postalar',
  tickets: 'Talepler',
  bulk_shift: 'Toplu Kaydırma',
  content_rules: 'İçerik Kuralları',
  jobs: "Job'lar",
  settings: 'Ayarlar',
  users: 'Kullanıcılar',
}

export const ALL_SCREENS = Object.keys(SCREEN_LABELS) as ScreenKey[]

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  yonetici: 'Yönetici',
  operator: 'Operatör',
  izleyici: 'İzleyici',
}

export const ALL_ROLES = Object.keys(ROLE_LABELS) as Role[]
