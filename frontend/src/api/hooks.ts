import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPostForm, apiPatch, apiPut, apiDelete, setCsrfToken, ApiError } from './client'
import type {
  StatusResponse,
  StatisticsResponse,
  MailLogsResponse,
  TicketsResponse,
  ErrorsResponse,
  TokenInfoResponse,
  EmailsResponse,
  RunProcessorResponse,
  TimeseriesResponse,
  ClassificationReportResponse,
  BySenderResponse,
  ProcessEmailResponse,
  ValidateTurkishIdResponse,
  ValidateTaxIdResponse,
  ProfanityCheckResponse,
  TicketDetailResponse,
  MailLogDetailResponse,
  ServiceLogsResponse,
  ServiceLogsSummaryResponse,
  BulkShiftEnvResponse,
  BulkShiftUploadResponse,
  CurrentUser,
  User,
  Role,
  ScreenKey,
  ScreensPayload,
} from '@/types/api'

function toQueryString(params: object) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(
    params as Record<string, string | number | undefined>,
  )) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const queryKeys = {
  status: ['status'] as const,
  statistics: ['statistics'] as const,
  mailLogs: (params: MailLogsParams) => ['mail-logs', params] as const,
  tickets: (params: TicketsParams) => ['tickets', params] as const,
  errors: ['errors'] as const,
  tokenInfo: ['token-info'] as const,
  emails: ['emails'] as const,
  serviceLogs: (params: ServiceLogsParams) => ['service-logs', params] as const,
  serviceLogsSummary: ['service-logs', 'summary'] as const,
  reportsTimeseries: (filters: ReportFilters) =>
    ['reports', 'timeseries', filters] as const,
  reportsByClassification: (filters: ReportFilters) =>
    ['reports', 'by-classification', filters] as const,
  reportsBySender: (filters: ReportFilters & { limit?: number }) =>
    ['reports', 'by-sender', filters] as const,
}

export interface ReportFilters {
  range?: string
  classification?: string
  sender?: string
}

interface PollOptions {
  /** Otomatik yenileme aralığı (ms). Verilmezse otomatik yenilenmez. */
  refetchInterval?: number
}

export function useStatus(options: PollOptions = {}) {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: () => apiGet<StatusResponse>('/api/status'),
    refetchInterval: options.refetchInterval,
  })
}

export function useStatistics(options: PollOptions = {}) {
  return useQuery({
    queryKey: queryKeys.statistics,
    queryFn: () => apiGet<StatisticsResponse>('/api/statistics'),
    refetchInterval: options.refetchInterval,
  })
}

export interface MailLogsParams {
  q?: string
  limit?: number
  offset?: number
  range?: string
  sender?: string
  classification?: string
  status?: string
  event?: string
}

export function useMailLogs(params: MailLogsParams & PollOptions = {}) {
  const { refetchInterval, ...filters } = params
  return useQuery({
    queryKey: queryKeys.mailLogs(filters),
    queryFn: () => apiGet<MailLogsResponse>(`/api/mail-logs${toQueryString(filters)}`),
    refetchInterval,
  })
}

export function useMailLogDetail(timestamp: string | undefined) {
  return useQuery({
    queryKey: ['mail-logs', 'detail', timestamp],
    queryFn: () =>
      apiGet<MailLogDetailResponse>(`/api/mail-logs/detail/${encodeURIComponent(timestamp!)}`),
    enabled: Boolean(timestamp),
  })
}

export interface TicketsParams {
  q?: string
  limit?: number
  offset?: number
  range?: string
  sender?: string
  classification?: string
}

export function useTickets(params: TicketsParams & PollOptions = {}) {
  const { q, limit, offset, range, sender, classification, refetchInterval } = params
  return useQuery({
    queryKey: queryKeys.tickets({ q, limit, offset, range, sender, classification }),
    queryFn: () =>
      apiGet<TicketsResponse>(
        `/api/tickets${toQueryString({ q, limit, offset, range, sender, classification })}`,
      ),
    refetchInterval,
  })
}

export function useTicket(ticketId: string | undefined) {
  return useQuery({
    queryKey: ['tickets', 'detail', ticketId],
    queryFn: () => apiGet<TicketDetailResponse>(`/api/tickets/${ticketId}`),
    enabled: Boolean(ticketId),
  })
}

export function useErrors(options: PollOptions = {}) {
  return useQuery({
    queryKey: queryKeys.errors,
    queryFn: () => apiGet<ErrorsResponse>('/api/errors'),
    refetchInterval: options.refetchInterval,
  })
}

export function useTokenInfo() {
  return useQuery({
    queryKey: queryKeys.tokenInfo,
    queryFn: () => apiGet<TokenInfoResponse>('/api/token/info'),
  })
}

export function useEmails() {
  return useQuery({
    queryKey: queryKeys.emails,
    queryFn: () => apiGet<EmailsResponse>('/api/emails'),
  })
}

export function useReportsTimeseries(filters: ReportFilters = {}) {
  return useQuery({
    queryKey: queryKeys.reportsTimeseries(filters),
    queryFn: () =>
      apiGet<TimeseriesResponse>(
        `/api/reports/timeseries${toQueryString(filters)}`,
      ),
  })
}

export function useReportsByClassification(
  filters: Pick<ReportFilters, 'range' | 'sender'> = {},
) {
  return useQuery({
    queryKey: queryKeys.reportsByClassification(filters),
    queryFn: () =>
      apiGet<ClassificationReportResponse>(
        `/api/reports/by-classification${toQueryString(filters)}`,
      ),
  })
}

export function useReportsBySender(
  filters: Pick<ReportFilters, 'range' | 'classification'> & { limit?: number } = {},
) {
  return useQuery({
    queryKey: queryKeys.reportsBySender(filters),
    queryFn: () =>
      apiGet<BySenderResponse>(`/api/reports/by-sender${toQueryString(filters)}`),
  })
}

export function useProcessEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) =>
      apiPost<ProcessEmailResponse>('/api/process-email', { email_id: emailId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.status })
      queryClient.invalidateQueries({ queryKey: ['mail-logs'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.emails })
    },
  })
}

export function useValidateTurkishId() {
  return useMutation({
    mutationFn: (idNumber: string) =>
      apiPost<ValidateTurkishIdResponse>('/api/validate/turkish-id', {
        id_number: idNumber,
      }),
  })
}

export function useValidateTaxId() {
  return useMutation({
    mutationFn: (taxId: string) =>
      apiPost<ValidateTaxIdResponse>('/api/validate/tax-id', { tax_id: taxId }),
  })
}

export function useCheckProfanity() {
  return useMutation({
    mutationFn: (text: string) =>
      apiPost<ProfanityCheckResponse>('/api/profanity-check', { text }),
  })
}

export function useRefreshToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<TokenInfoResponse>('/api/token/refresh'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tokenInfo })
    },
  })
}

export function useRunProcessor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<RunProcessorResponse>('/api/run'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.status })
      queryClient.invalidateQueries({ queryKey: queryKeys.statistics })
      queryClient.invalidateQueries({ queryKey: ['mail-logs'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })
}

export function useClearErrors() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<{ success: boolean }>('/api/clear-errors'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.errors })
    },
  })
}

export function useClearMailLogs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<{ success: boolean }>('/api/mail-logs/clear'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mail-logs'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })
}

export interface ServiceLogsParams {
  service?: string
  actor?: string
  status?: string
  range?: string
  limit?: number
  offset?: number
}

export function useServiceLogs(params: ServiceLogsParams & PollOptions = {}) {
  const { refetchInterval, ...filters } = params
  return useQuery({
    queryKey: queryKeys.serviceLogs(filters),
    queryFn: () =>
      apiGet<ServiceLogsResponse>(`/api/service-logs${toQueryString(filters)}`),
    refetchInterval,
  })
}

export function useServiceLogsSummary(options: PollOptions = {}) {
  return useQuery({
    queryKey: queryKeys.serviceLogsSummary,
    queryFn: () => apiGet<ServiceLogsSummaryResponse>('/api/service-logs/summary'),
    refetchInterval: options.refetchInterval,
  })
}

export function useClearServiceLogs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<{ success: boolean }>('/api/service-logs/clear'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-logs'] })
    },
  })
}

export function useBulkShiftEnv() {
  return useQuery({
    queryKey: ['bulk-shift', 'env'],
    queryFn: () => apiGet<BulkShiftEnvResponse>('/api/bulk-shift/env'),
  })
}

export interface BulkShiftUploadInput {
  file: File
  /** Optional -- only used as a fallback for rows whose own parentTicketUUID
   * column (in the Excel) is blank. Reporter is always the fixed "Onay
   * Kaydırma" CSM contact, not collected here. */
  parentTicketUuid?: string
}

export function useUploadBulkShift() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BulkShiftUploadInput) => {
      const formData = new FormData()
      formData.append('file', input.file)
      if (input.parentTicketUuid) {
        formData.append('parent_ticket_uuid', input.parentTicketUuid)
      }
      return apiPostForm<BulkShiftUploadResponse>('/api/bulk-shift/upload', formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-logs'] })
    },
  })
}

// ==========================================================
// Auth / kullanıcı yönetimi
// ==========================================================

/** /api/auth/me: 401 (henüz giriş yapılmamış) bir hata DEĞİL, sadece
 * "kullanıcı yok" anlamına gelir -- useAuth bunu normal bir durum olarak
 * ele alır, RequireAuth bu durumda /login'e yönlendirir. */
export function useCurrentUser() {
  return useQuery<CurrentUser | null>({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        const user = await apiGet<CurrentUser>('/api/auth/me')
        setCsrfToken(user.csrf_token)
        return user
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          setCsrfToken(null)
          return null
        }
        throw e
      }
    },
    retry: false,
    staleTime: 5 * 60_000,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { email: string; password: string }) =>
      apiPost<CurrentUser>('/api/auth/login', input),
    onSuccess: (user) => {
      setCsrfToken(user.csrf_token)
      queryClient.setQueryData(['auth', 'me'], user)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost('/api/auth/logout'),
    onSuccess: () => {
      setCsrfToken(null)
      queryClient.setQueryData(['auth', 'me'], null)
      queryClient.clear()
    },
  })
}

export function useUsers() {
  return useQuery<{ users: User[] }>({
    queryKey: ['users'],
    queryFn: () => apiGet('/api/users'),
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { email: string; password: string; role: Role }) =>
      apiPost<User>('/api/users', input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...input }: { id: number; role?: Role; is_active?: boolean; password?: string }) =>
      apiPatch<User>(`/api/users/${id}`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useDeactivateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/users/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUserOverrides(userId: number | null) {
  return useQuery<ScreensPayload>({
    queryKey: ['users', userId, 'overrides'],
    queryFn: () => apiGet(`/api/users/${userId}/overrides`),
    enabled: userId !== null,
  })
}

export function useSetUserOverrides() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, overrides }: { userId: number; overrides: Record<ScreenKey, boolean | null> }) =>
      apiPut<ScreensPayload>(`/api/users/${userId}/overrides`, { overrides }),
    onSuccess: (_data, { userId }) =>
      queryClient.invalidateQueries({ queryKey: ['users', userId, 'overrides'] }),
  })
}
