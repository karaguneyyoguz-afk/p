import type { MailLogEntry } from '@/types/api'

const PROCESSED_EVENTS = new Set([
  'ticket_created',
  'ticket_not_created',
  'email_processed',
])

export function topLevelCategory(classification?: string): string {
  if (!classification) return 'Diğer'
  const [first] = classification.split('>')
  return first.trim() || 'Diğer'
}

const CATEGORY_LABELS: Record<string, string> = {
  BACKOFFICE_ISLEMLERI: 'Backoffice İşlemleri',
  BILGI_ISTEK: 'Bilgi İsteği',
  SIKAYET: 'Şikayet',
  TESEKKUR: 'Teşekkür',
  rejected_content: 'Reddedilen İçerik',
  phishing_suspect: 'Phishing Şüphesi',
  Diğer: 'Diğer',
}

export function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key
}

export type CategoryTone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const CATEGORY_TONES: Record<string, CategoryTone> = {
  BACKOFFICE_ISLEMLERI: 'warning',
  BILGI_ISTEK: 'primary',
  SIKAYET: 'danger',
  TESEKKUR: 'success',
  rejected_content: 'danger',
  phishing_suspect: 'danger',
}

export function categoryTone(key: string): CategoryTone {
  return CATEGORY_TONES[key] ?? 'neutral'
}

const ACTOR_LABELS: Record<string, string> = {
  sistem: 'Sistem (otomatik)',
  panel: 'Panel',
  cli: 'CLI',
}

/** There is no login system — "actor" is just which entry-point process ran
 * the code (watch_mail.py, app.py, or a direct `python main.py`), not a human
 * user account. */
export function actorLabel(actor?: string): string {
  if (!actor) return 'Bilinmiyor'
  return ACTOR_LABELS[actor] ?? actor
}

export function actorTone(actor?: string): CategoryTone {
  if (actor === 'sistem') return 'info'
  if (actor === 'panel') return 'primary'
  if (actor === 'cli') return 'neutral'
  return 'neutral'
}

const EVENT_LABELS: Record<string, string> = {
  ticket_created: 'Ticket Oluşturuldu',
  ticket_not_created: 'Ticket Oluşturulamadı',
  email_processed: 'E-posta İşlendi',
  email_fetch: 'E-posta Alınamadı',
  processor_error: 'Sistem Hatası',
}

export function eventLabel(event: string): string {
  return EVENT_LABELS[event] ?? event
}

/** Formats a 'YYYY-MM-DD' key as 'DD/MM' via string ops only — avoids re-parsing as a UTC Date. */
export function formatDayLabel(dateKey: string): string {
  const [, m, d] = dateKey.split('-')
  return m && d ? `${d}/${m}` : dateKey
}

export interface DailyVolumePoint {
  date: string
  label: string
  count: number
}

function localDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function groupByDay(
  logs: MailLogEntry[],
  days = 14,
): DailyVolumePoint[] {
  const buckets = new Map<string, { count: number; date: Date }>()
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    buckets.set(localDateKey(d), { count: 0, date: d })
  }

  for (const log of logs) {
    if (!PROCESSED_EVENTS.has(log.event)) continue
    // Backend timestamps embed the local offset already (e.g. 2026-08-23T14:43:51+03:00),
    // so slicing gives the correct local calendar date without re-parsing as UTC.
    const key = log.timestamp?.slice(0, 10)
    const bucket = key && buckets.get(key)
    if (bucket) bucket.count += 1
  }

  return Array.from(buckets.entries()).map(([date, { count, date: d }]) => ({
    date,
    label: d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' }),
    count,
  }))
}

export interface CategorySlice {
  name: string
  value: number
}

export function groupByClassification(
  logs: MailLogEntry[],
  topN = 5,
): CategorySlice[] {
  const counts = new Map<string, number>()

  for (const log of logs) {
    if (log.event !== 'ticket_created') continue
    const key = categoryLabel(topLevelCategory(log.classification))
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }

  const sorted = Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  if (sorted.length <= topN) return sorted

  const top = sorted.slice(0, topN)
  const restTotal = sorted.slice(topN).reduce((sum, s) => sum + s.value, 0)
  return [...top, { name: 'Diğer', value: restTotal }]
}

export function recentActivity(
  logs: MailLogEntry[],
  limit = 8,
): MailLogEntry[] {
  return [...logs]
    .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
    .slice(0, limit)
}
