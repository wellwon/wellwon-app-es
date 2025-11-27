/**
 * Company domain React Query hooks
 * Replaces CompanyService and CompanyLogoService
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as companyApi from '@/api/company';
import { queryKeys } from '@/lib/queryKeys';

// Re-export types
export type {
  CompanyDetail,
  CompanySummary,
  UserCompanyInfo,
  CompanyUserInfo,
  BalanceInfo,
  BalanceTransaction,
  TelegramSupergroupInfo,
  CreateCompanyRequest,
  UpdateCompanyRequest,
} from '@/api/company';

// =============================================================================
// Company Queries
// =============================================================================

/**
 * Fetch all companies
 */
export function useCompanies(options?: {
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: queryKeys.companies.lists(),
    queryFn: () => companyApi.getCompanies(
      options?.includeArchived ?? false,
      options?.limit ?? 50,
      options?.offset ?? 0
    ),
  });
}

/**
 * Fetch single company by ID
 */
export function useCompany(companyId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.companies.detail(companyId || ''),
    queryFn: () => companyApi.getCompanyById(companyId!),
    enabled: !!companyId,
  });
}

/**
 * Fetch company by VAT
 */
export function useCompanyByVat(vat: string | undefined) {
  return useQuery({
    queryKey: ['companies', 'by-vat', vat],
    queryFn: () => companyApi.getCompanyByVat(vat!),
    enabled: !!vat,
  });
}

/**
 * Search companies
 */
export function useSearchCompanies(searchTerm: string, limit: number = 20) {
  return useQuery({
    queryKey: ['companies', 'search', searchTerm, limit],
    queryFn: () => companyApi.searchCompanies(searchTerm, limit),
    enabled: searchTerm.length >= 2,
  });
}

/**
 * Fetch current user's companies
 */
export function useMyCompanies(includeArchived: boolean = false) {
  return useQuery({
    queryKey: queryKeys.companies.list({ userId: 'me' }),
    queryFn: () => companyApi.getMyCompanies(includeArchived),
  });
}

// =============================================================================
// Company Users
// =============================================================================

/**
 * Fetch company users
 */
export function useCompanyUsers(companyId: string | undefined, includeInactive: boolean = false) {
  return useQuery({
    queryKey: queryKeys.companies.participants(companyId || ''),
    queryFn: () => companyApi.getCompanyUsers(companyId!, includeInactive),
    enabled: !!companyId,
  });
}

/**
 * Fetch user-company relationship
 */
export function useUserCompanyRelationship(companyId: string | undefined, userId: string | undefined) {
  return useQuery({
    queryKey: ['companies', companyId, 'users', userId, 'relationship'],
    queryFn: () => companyApi.getUserCompanyRelationship(companyId!, userId!),
    enabled: !!companyId && !!userId,
  });
}

// =============================================================================
// Telegram Integration
// =============================================================================

/**
 * Fetch company's Telegram groups
 */
export function useCompanyTelegramGroups(companyId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.companies.supergroups(companyId || ''),
    queryFn: () => companyApi.getCompanyTelegramGroups(companyId!),
    enabled: !!companyId,
  });
}

// =============================================================================
// Balance
// =============================================================================

/**
 * Fetch company balance
 */
export function useCompanyBalance(companyId: string | undefined) {
  return useQuery({
    queryKey: ['companies', companyId, 'balance'],
    queryFn: () => companyApi.getCompanyBalance(companyId!),
    enabled: !!companyId,
  });
}

/**
 * Fetch balance history
 */
export function useBalanceHistory(companyId: string | undefined, options?: {
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['companies', companyId, 'balance', 'history', options],
    queryFn: () => companyApi.getBalanceHistory(
      companyId!,
      options?.limit ?? 50,
      options?.offset ?? 0
    ),
    enabled: !!companyId,
  });
}

// =============================================================================
// Company Mutations
// =============================================================================

/**
 * Create a new company
 */
export function useCreateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: companyApi.createCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.all });
    },
  });
}

/**
 * Update a company
 */
export function useUpdateCompany(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: companyApi.UpdateCompanyRequest) =>
      companyApi.updateCompany(companyId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.detail(companyId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.lists() });
    },
  });
}

/**
 * Archive a company
 */
export function useArchiveCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, reason }: { companyId: string; reason?: string }) =>
      companyApi.archiveCompany(companyId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.all });
    },
  });
}

/**
 * Restore an archived company
 */
export function useRestoreCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: companyApi.restoreCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.all });
    },
  });
}

/**
 * Delete a company
 */
export function useDeleteCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: companyApi.deleteCompany,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.all });
    },
  });
}

// =============================================================================
// User Management Mutations
// =============================================================================

/**
 * Add user to company
 */
export function useAddUserToCompany(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: companyApi.AddUserRequest) =>
      companyApi.addUserToCompany(companyId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.participants(companyId) });
    },
  });
}

/**
 * Remove user from company
 */
export function useRemoveUserFromCompany(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason?: string }) =>
      companyApi.removeUserFromCompany(companyId, userId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.participants(companyId) });
    },
  });
}

/**
 * Change user role in company
 */
export function useChangeUserRole(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, newRole }: { userId: string; newRole: string }) =>
      companyApi.changeUserRole(companyId, userId, { new_relationship_type: newRole }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.participants(companyId) });
    },
  });
}

// =============================================================================
// Telegram Mutations
// =============================================================================

/**
 * Create Telegram group for company
 */
export function useCreateTelegramGroup(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => companyApi.createTelegramGroup(companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.supergroups(companyId) });
    },
  });
}

/**
 * Link existing Telegram group to company
 */
export function useLinkTelegramGroup(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (telegramGroupId: number) =>
      companyApi.linkTelegramGroup(companyId, telegramGroupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.supergroups(companyId) });
    },
  });
}

/**
 * Unlink Telegram group from company
 */
export function useUnlinkTelegramGroup(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (telegramGroupId: number) =>
      companyApi.unlinkTelegramGroup(companyId, telegramGroupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.supergroups(companyId) });
    },
  });
}

// =============================================================================
// Balance Mutations
// =============================================================================

/**
 * Update company balance
 */
export function useUpdateCompanyBalance(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: companyApi.UpdateBalanceRequest) =>
      companyApi.updateCompanyBalance(companyId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies', companyId, 'balance'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.detail(companyId) });
    },
  });
}

// =============================================================================
// Logo Mutations
// =============================================================================

/**
 * Upload company logo
 */
export function useUploadCompanyLogo(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => companyApi.uploadCompanyLogo(companyId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.detail(companyId) });
    },
  });
}

/**
 * Delete company logo
 */
export function useDeleteCompanyLogo(companyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (logoUrl: string) => companyApi.deleteCompanyLogo(companyId, logoUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.companies.detail(companyId) });
    },
  });
}
