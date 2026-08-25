export interface StatusResponse {
  is_running: boolean
  last_run: string | null
  total_emails_processed: number
  total_tickets_created: number
  errors_count: number
  current_time: string
}

export interface StatisticsResponse {
  total_emails_processed: number
  total_tickets_created: number
  success_rate: number
  total_errors: number
  last_run: string | null
}

export type MailLogStatus = 'success' | 'failed' | 'blocked' | 'rejected' | string

export interface TicketDetails {
  ticket_type?: number
  category?: number
  sub_category?: number
  sub_category_code?: string
  body_preview?: string
  // Toplu kaydırma (mail-tetikli) özet alanları -- bulk_shift.process_rows'un
  // döndürdüğü summary dict'i bu şekle sahip.
  environment?: string
  total?: number
  success_count?: number
  failed_count?: number
  results?: BulkShiftResultRow[]
}

export type Actor = 'sistem' | 'panel' | 'cli' | string

export interface MailLogEntry {
  timestamp: string
  event: string
  status: MailLogStatus
  actor?: Actor
  sender_email?: string
  subject?: string
  reason?: string
  details?: string
  classification?: string
  ticket_id?: string
  ticket_details?: TicketDetails
  mail_body?: string
}

export interface MailLogsResponse {
  logs: MailLogEntry[]
  total: number
  limit: number
  offset: number
}

export interface MailLogDetailResponse {
  log: MailLogEntry
}

export interface TicketsResponse {
  tickets: MailLogEntry[]
  total: number
  limit: number
  offset: number
}

export interface TicketDetailResponse {
  ticket: MailLogEntry
}

export interface ErrorEntry {
  timestamp: string
  error: string
  details?: string
  sender_email?: string
  subject?: string
  status?: string
}

export interface ErrorsResponse {
  errors: ErrorEntry[]
}

export interface TokenInfo {
  token?: string
  acquired_at?: string
  expires_in?: string
  error?: string
}

export interface TokenInfoResponse {
  token_info: TokenInfo
}

export interface EmailListItem {
  id: string
  from: string
  subject: string
  preview: string
  received: string
  is_unread: boolean
}

export interface EmailsResponse {
  emails: EmailListItem[]
  count: number
}

export interface RunProcessorResponse {
  success: boolean
  processed?: number
  message?: string
  error?: string
}

export interface TimeseriesPoint {
  date: string
  count: number
  success_count: number
  error_count: number
}

export interface TimeseriesResponse {
  granularity: 'day' | 'hour'
  range: string
  points: TimeseriesPoint[]
}

export interface ClassificationCategory {
  name: string
  count: number
}

export interface ClassificationReportResponse {
  categories: ClassificationCategory[]
}

export interface SenderCount {
  sender_email: string
  count: number
}

export interface BySenderResponse {
  senders: SenderCount[]
}

export interface ProcessEmailResponse {
  success: boolean
  ticket_id?: string | null
  classification?: string
  sender?: string
  email?: string
  message?: string
}

export interface ValidateTurkishIdResponse {
  id_number: string
  is_valid: boolean
}

export interface ValidateTaxIdResponse {
  tax_id: string
  is_valid: boolean
}

export interface ProfanityCheckResponse {
  text_preview: string
  has_profanity: boolean
}

export type ServiceName = 'csm_api' | 'gmail_imap' | 'panel_api'

export interface ServiceLogEntry {
  timestamp: string
  service: ServiceName
  action: string
  actor: Actor
  status: 'success' | 'failed'
  detail?: string
  duration_ms?: number | null
}

export interface ServiceLogsResponse {
  logs: ServiceLogEntry[]
  total: number
  limit: number
  offset: number
}

export interface ServiceHealthSummary {
  total: number
  success_count: number
  failed_count: number
  last_success_at: string | null
  last_failure_at: string | null
}

export interface ServiceLogsSummaryResponse {
  services: Record<ServiceName, ServiceHealthSummary>
  actors: Record<string, number>
}

export interface BulkShiftEnvResponse {
  environment: 'preprod' | 'prod'
}

export interface BulkShiftResultRow {
  reservation_no: string
  shift_type: string
  shift_type_code: string
  success: boolean
  ticket_id?: string | null
  error?: string | null
}

export interface BulkShiftUploadResponse {
  environment: string
  total: number
  success_count: number
  failed_count: number
  results: BulkShiftResultRow[]
}

// ==========================================================
// Auth / kullanıcı yönetimi
// ==========================================================

export type Role = 'admin' | 'yonetici' | 'operator' | 'izleyici'

export type ScreenKey =
  | 'dashboard'
  | 'reports'
  | 'monitoring'
  | 'logs'
  | 'emails'
  | 'tickets'
  | 'bulk_shift'
  | 'settings'
  | 'users'

export interface ScreenOverride {
  screen_key: ScreenKey
  allow: boolean
}

export interface User {
  id: number
  email: string
  role: Role
  is_active: boolean
  created_at: string | null
}

/** Response shape for /api/auth/me AND /api/auth/login (same payload). */
export interface CurrentUser extends User {
  role_screens: ScreenKey[]
  effective_screens: ScreenKey[]
  overrides: ScreenOverride[]
  csrf_token: string
}

/** Response shape for /api/users/<id>/overrides (GET and PUT). */
export interface ScreensPayload {
  role: Role
  role_screens: ScreenKey[]
  effective_screens: ScreenKey[]
  overrides: ScreenOverride[]
}
