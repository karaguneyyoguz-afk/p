import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { RequireScreen } from '@/components/auth/RequireScreen'
import { Login } from '@/pages/Login'
import { Forbidden } from '@/pages/Forbidden'

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
const Users = lazy(() => import('@/pages/Users').then((m) => ({ default: m.Users })))

function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="login" element={<Login />} />

        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route
              index
              element={
                <RequireScreen screen="dashboard">
                  <Dashboard />
                </RequireScreen>
              }
            />
            <Route
              path="reports"
              element={
                <RequireScreen screen="reports">
                  <Reports />
                </RequireScreen>
              }
            />
            <Route
              path="emails"
              element={
                <RequireScreen screen="emails">
                  <Emails />
                </RequireScreen>
              }
            />
            <Route
              path="tickets"
              element={
                <RequireScreen screen="tickets">
                  <Tickets />
                </RequireScreen>
              }
            />
            <Route
              path="tickets/:ticketId"
              element={
                <RequireScreen screen="tickets">
                  <TicketDetail />
                </RequireScreen>
              }
            />
            <Route
              path="logs"
              element={
                <RequireScreen screen="logs">
                  <Logs />
                </RequireScreen>
              }
            />
            <Route
              path="logs/:timestamp"
              element={
                <RequireScreen screen="logs">
                  <LogDetail />
                </RequireScreen>
              }
            />
            <Route
              path="monitoring"
              element={
                <RequireScreen screen="monitoring">
                  <Monitoring />
                </RequireScreen>
              }
            />
            <Route
              path="bulk-shift"
              element={
                <RequireScreen screen="bulk_shift">
                  <BulkShift />
                </RequireScreen>
              }
            />
            <Route
              path="settings"
              element={
                <RequireScreen screen="settings">
                  <Settings />
                </RequireScreen>
              }
            />
            <Route
              path="users"
              element={
                <RequireScreen screen="users">
                  <Users />
                </RequireScreen>
              }
            />
            <Route path="403" element={<Forbidden />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
