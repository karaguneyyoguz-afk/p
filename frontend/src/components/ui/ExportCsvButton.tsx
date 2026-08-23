import { Download } from 'lucide-react'
import { downloadCsv } from '@/lib/csv'

export function ExportCsvButton({
  filename,
  rows,
}: {
  filename: string
  rows: (string | number)[][]
}) {
  return (
    <button
      type="button"
      onClick={() => downloadCsv(filename, rows)}
      title="CSV olarak indir"
      className="flex items-center gap-1.5 rounded-lg border border-enigma-border px-2.5 py-1.5 text-xs font-medium text-enigma-text-muted hover:bg-enigma-bg hover:text-enigma-text"
    >
      <Download className="h-3.5 w-3.5" />
      CSV
    </button>
  )
}
