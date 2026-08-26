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
  // false -> bağımsız "ana ticket" (BO/YÇM, parentTicketUUID hiç verilmedi);
  // true -> mevcut bir ticket'a bağlı "ilişkili ticket" (Eos/wtatil).
  is_linked: boolean
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
  // Yüklenen dosya "Yeni Ticket ID"/"Servis Durumu"/"Servis Mesajı"
  // sütunlarını içeriyorsa (BO/YÇM şablonu), bu sütunlar doldurulmuş hâliyle
  // base64 .xlsx olarak döner -- yoksa (Eos/wtatil) ikisi de yoktur.
  result_file_base64?: string
  result_file_name?: string
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
  | 'content_rules'
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

// ==========================================================
// İçerik denetimi (uygunsuz içerik kuralları + işaretlenmiş mailler)
// ==========================================================

export type ContentRuleType = 'keyword' | 'regex'
export type ContentRuleCategory = 'kufur' | 'spam' | 'tehdit' | 'yetiskin' | 'diger'

export interface ContentRule {
  id: number
  pattern: string
  rule_type: ContentRuleType
  category: ContentRuleCategory
  is_active: boolean
  created_by_id: number | null
  created_at: string
  updated_at: string
}

export interface ContentRulesResponse {
  rules: ContentRule[]
  categories: ContentRuleCategory[]
  types: ContentRuleType[]
}

export interface ContentRuleTestResponse {
  matched: boolean
  category: ContentRuleCategory | null
  rule_source: 'config' | 'db' | null
  snippet: string | null
}

export type FlaggedMailStatus = 'pending' | 'approved' | 'rejected'

export interface FlaggedMail {
  id: number
  sender_email: string
  sender_name: string | null
  subject: string
  mail_body: string
  matched_category: ContentRuleCategory
  matched_rule_source: 'config' | 'db'
  matched_rule_id: number | null
  matched_pattern: string | null
  matched_snippet: string | null
  status: FlaggedMailStatus
  reviewed_by_id: number | null
  reviewed_at: string | null
  created_at: string
}

export interface FlaggedMailsResponse {
  flagged_mails: FlaggedMail[]
  total: number
  limit: number
  offset: number
}

export interface FlaggedMailDetailResponse {
  flagged_mail: FlaggedMail
}
