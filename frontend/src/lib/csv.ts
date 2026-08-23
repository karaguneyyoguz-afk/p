function toCsvCell(value: string | number): string {
  const text = String(value ?? '')
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function downloadCsv(filename: string, rows: (string | number)[][]) {
  const csv = rows.map((row) => row.map(toCsvCell).join(',')).join('\r\n')
  // Leading BOM so Excel detects UTF-8 and renders Turkish characters correctly.
  const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
