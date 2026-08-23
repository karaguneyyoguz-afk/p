import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'

const Dashboard = lazy(() =>
  import('@/pages/Dashboard').then((m) => ({ default: m.Dashboard })),
)
const Reports = lazy(() =>
  import('@/pages/Reports').then((m) => ({ default: m.Reports })),
)
const Emails = lazy(() =>
  import('@/pages/Emails').then((m) => ({ default: m.Emails })),
)
const Tickets = lazy(() =>
  import('@/pages/Tickets').then((m) => ({ default: m.Tickets })),
)
const TicketDetail = lazy(() =>
  import('@/pages/TicketDetail').then((m) => ({ default: m.TicketDetail })),
)
const Logs = lazy(() => import('@/pages/Logs').then((m) => ({ default: m.Logs })))
const LogDetail = lazy(() =>
  import('@/pages/LogDetail').then((m) => ({ default: m.LogDetail })),
)
const Monitoring = lazy(() =>
  import('@/pages/Monitoring').then((m) => ({ default: m.Monitoring })),
)
const BulkShift = lazy(() =>
  import('@/pages/BulkShift').then((m) => ({ default: m.BulkShift })),
)
const Settings = lazy(() =>
  import('@/pages/Settings').then((m) => ({ default: m.Settings })),
)

function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="reports" element={<Reports />} />
          <Route path="emails" element={<Emails />} />
          <Route path="tickets" element={<Tickets />} />
          <Route path="tickets/:ticketId" element={<TicketDetail />} />
          <Route path="logs" element={<Logs />} />
          <Route path="logs/:timestamp" element={<LogDetail />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="bulk-shift" element={<BulkShift />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
