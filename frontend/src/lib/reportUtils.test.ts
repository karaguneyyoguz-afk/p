import { describe, it, expect } from 'vitest'
import {
  groupByDay,
  groupByClassification,
  topLevelCategory,
  categoryLabel,
  formatDayLabel,
  recentActivity,
  actorLabel,
  actorTone,
  eventLabel,
} from './reportUtils'
import type { MailLogEntry } from '@/types/api'

function log(overrides: Partial<MailLogEntry>): MailLogEntry {
  return {
    timestamp: '2026-08-23T10:00:00+03:00',
    event: 'ticket_created',
    status: 'success',
    ...overrides,
  }
}

describe('groupByDay', () => {
  it("buckets today's events under today's local calendar date, not UTC", () => {
    // Regression test: Date.toISOString() converts to UTC before slicing, which
    // shifted the local midnight bucket back a day for positive UTC offsets
    // (e.g. Turkey, +03:00) — today's events silently landed in "yesterday".
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    const todayKey = `${y}-${m}-${d}`

    const logs = [log({ timestamp: `${todayKey}T09:00:00+03:00` })]
    const buckets = groupByDay(logs, 3)
    const todayBucket = buckets.find((b) => b.date === todayKey)

    expect(todayBucket).toBeDefined()
    expect(todayBucket?.count).toBe(1)
  })

  it('produces exactly `days` buckets ending today, all zero when there are no logs', () => {
    const buckets = groupByDay([], 7)
    expect(buckets).toHaveLength(7)
    expect(buckets.every((b) => b.count === 0)).toBe(true)
  })

  it('only counts processed event types (ticket_created/ticket_not_created/email_processed)', () => {
    const logs = [
      log({ event: 'ticket_created' }),
      log({ event: 'email_fetch' }), // not a "processed" event — should be ignored
      log({ event: 'processor_error' }), // not a "processed" event — should be ignored
    ]
    const buckets = groupByDay(logs, 1)
    expect(buckets[0].count).toBe(1)
  })

  it('ignores events whose date falls outside the requested window', () => {
    const logs = [log({ timestamp: '2020-01-01T10:00:00+03:00' })]
    const buckets = groupByDay(logs, 3)
    expect(buckets.every((b) => b.count === 0)).toBe(true)
  })
})

describe('formatDayLabel', () => {
  it('formats YYYY-MM-DD as DD/MM via string ops (no Date re-parsing)', () => {
    expect(formatDayLabel('2026-08-23')).toBe('23/08')
    expect(formatDayLabel('2026-01-05')).toBe('05/01')
  })
})

describe('topLevelCategory / categoryLabel', () => {
  it('takes the segment before the first ">"', () => {
    expect(topLevelCategory('BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI')).toBe(
      'BACKOFFICE_ISLEMLERI',
    )
  })

  it('falls back to "Diğer" for empty/missing classification', () => {
    expect(topLevelCategory(undefined)).toBe('Diğer')
    expect(topLevelCategory('')).toBe('Diğer')
  })

  it('maps known keys to Turkish labels and passes through unknown ones', () => {
    expect(categoryLabel('BILGI_ISTEK')).toBe('Bilgi İsteği')
    expect(categoryLabel('SOMETHING_UNMAPPED')).toBe('SOMETHING_UNMAPPED')
  })
})

describe('groupByClassification', () => {
  it('counts ticket_created events by top-level category, sorted descending', () => {
    const logs = [
      log({ classification: 'BILGI_ISTEK > A' }),
      log({ classification: 'BILGI_ISTEK > B' }),
      log({ classification: 'SIKAYET > A' }),
      log({ event: 'ticket_not_created', classification: 'BILGI_ISTEK > C' }), // excluded
    ]
    const result = groupByClassification(logs)
    expect(result[0]).toEqual({ name: 'Bilgi İsteği', value: 2 })
    expect(result[1]).toEqual({ name: 'Şikayet', value: 1 })
  })

  it('groups everything past topN into a single "Diğer" bucket', () => {
    const logs = Array.from({ length: 6 }, (_, i) =>
      log({ classification: `CAT_${i} > x` }),
    )
    const result = groupByClassification(logs, 5)
    expect(result).toHaveLength(6) // 5 named + 1 "Diğer"
    expect(result.at(-1)?.name).toBe('Diğer')
    expect(result.at(-1)?.value).toBe(1)
  })
})

describe('recentActivity', () => {
  it('sorts newest first and caps at the given limit', () => {
    const logs = [
      log({ timestamp: '2026-08-20T10:00:00+03:00' }),
      log({ timestamp: '2026-08-23T10:00:00+03:00' }),
      log({ timestamp: '2026-08-21T10:00:00+03:00' }),
    ]
    const result = recentActivity(logs, 2)
    expect(result).toHaveLength(2)
    expect(result[0].timestamp).toBe('2026-08-23T10:00:00+03:00')
    expect(result[1].timestamp).toBe('2026-08-21T10:00:00+03:00')
  })
})

describe('actorLabel / actorTone', () => {
  it('maps known actors to Turkish labels', () => {
    expect(actorLabel('sistem')).toBe('Sistem (otomatik)')
    expect(actorLabel('panel')).toBe('Panel')
    expect(actorLabel('cli')).toBe('CLI')
  })

  it('falls back to "Bilinmiyor" for missing actor (pre-instrumentation records)', () => {
    expect(actorLabel(undefined)).toBe('Bilinmiyor')
  })

  it('passes through an unrecognized actor value as-is', () => {
    expect(actorLabel('gizemli-surec')).toBe('gizemli-surec')
  })

  it('gives each known actor a distinct tone', () => {
    expect(actorTone('sistem')).toBe('info')
    expect(actorTone('panel')).toBe('primary')
    expect(actorTone('cli')).toBe('neutral')
  })
})

describe('eventLabel', () => {
  it('maps known events to Turkish labels', () => {
    expect(eventLabel('ticket_created')).toBe('Ticket Oluşturuldu')
    expect(eventLabel('processor_error')).toBe('Sistem Hatası')
  })

  it('passes through an unrecognized event as-is', () => {
    expect(eventLabel('some_new_event')).toBe('some_new_event')
  })
})
