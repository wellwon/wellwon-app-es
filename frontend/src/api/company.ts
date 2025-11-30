// =============================================================================
// File: src/api/company.ts — Company Domain API Client
// =============================================================================

import { API } from "./core";

// -----------------------------------------------------------------------------
// Types (matching backend company queries and API models)
// -----------------------------------------------------------------------------

export interface CompanyDetail {
  id: string;
  name: string;
  company_type: string;
  created_by: string;
  created_at: string;
  updated_at: string | null;
  is_active: boolean;
  // Legal info
  vat: string | null;
  ogrn: string | null;
  kpp: string | null;
  // Address
  postal_code: string | null;
  country_id: number;
  city: string | null;
  street: string | null;
  // Contacts
  director: string | null;
  email: string | null;
  phone: string | null;
  // Telegram contacts
  tg_dir: string | null;
  tg_accountant: string | null;
  tg_manager_1: string | null;
  tg_manager_2: string | null;
  tg_manager_3: string | null;
  tg_support: string | null;
  // Balance
  balance: string;
  // Counts
  user_count: number;
}

export interface CompanySummary {
  id: string;
  name: string;
  company_type: string;
  vat: string | null;
  city: string | null;
  user_count: number;
  balance: string;
  is_active: boolean;
}

export interface UserCompanyInfo {
  company_id: string;
  user_id: string;
  relationship_type: string;
  joined_at: string;
  is_active: boolean;
  company_name: string | null;
  company_type: string | null;
}

export interface CompanyUserInfo {
  user_id: string;
  relationship_type: string;
  joined_at: string;
  is_active: boolean;
  user_name: string | null;
  user_email: string | null;
  user_phone: string | null;
}

export interface TelegramSupergroupInfo {
  telegram_group_id: number;
  title: string;
  username: string | null;
  description: string | null;
  invite_link: string | null;
  is_forum: boolean;
  created_at: string;
}

export interface BalanceInfo {
  company_id: string;
  balance: string;
  last_updated: string | null;
}

export interface BalanceTransaction {
  id: string;
  company_id: string;
  old_balance: string;
  new_balance: string;
  change_amount: string;
  reason: string;
  reference_id: string | null;
  updated_by: string;
  created_at: string;
}

export interface UserCompanyRelationship {
  company_id: string;
  user_id: string;
  is_member: boolean;
  relationship_type: string | null;
  joined_at: string | null;
}

// Request types
export interface CreateCompanyRequest {
  name: string;
  company_type?: string;
  vat?: string;
  ogrn?: string;
  kpp?: string;
  postal_code?: string;
  country_id?: number;
  city?: string;
  street?: string;
  director?: string;
  email?: string;
  phone?: string;
  tg_dir?: string;
  tg_accountant?: string;
  tg_manager_1?: string;
  tg_manager_2?: string;
  tg_manager_3?: string;
  tg_support?: string;
  // Saga orchestration options
  // If true, CompanyCreationSaga will create Telegram group automatically
  create_telegram_group?: boolean;
  telegram_group_title?: string;
  telegram_group_description?: string;
  // If true, saga will create company chat (default: true for backward compat)
  create_chat?: boolean;
  // If provided, saga will link this existing chat to the company instead of creating new
  link_chat_id?: string;
}

export interface UpdateCompanyRequest {
  name?: string;
  company_type?: string;
  vat?: string;
  ogrn?: string;
  kpp?: string;
  postal_code?: string;
  country_id?: number;
  city?: string;
  street?: string;
  director?: string;
  email?: string;
  phone?: string;
  tg_dir?: string;
  tg_accountant?: string;
  tg_manager_1?: string;
  tg_manager_2?: string;
  tg_manager_3?: string;
  tg_support?: string;
}

export interface AddUserRequest {
  user_id: string;
  relationship_type?: string;
}

export interface ChangeUserRoleRequest {
  new_relationship_type: string;
}

export interface UpdateBalanceRequest {
  change_amount: string;
  reason: string;
  reference_id?: string;
}

// Response wrapper for command results
export interface CommandResponse {
  id: string;
  status: string;
  message?: string;
}

// -----------------------------------------------------------------------------
// Company CRUD Operations
// -----------------------------------------------------------------------------

export async function getCompanies(
  includeArchived: boolean = false,
  limit: number = 50,
  offset: number = 0
): Promise<CompanySummary[]> {
  const { data } = await API.get<CompanySummary[]>("/companies", {
    params: {
      include_archived: includeArchived,
      limit,
      offset,
    },
  });
  return data;
}

export async function getCompanyById(companyId: string): Promise<CompanyDetail> {
  const { data } = await API.get<CompanyDetail>(`/companies/${companyId}`);
  return data;
}

export async function createCompany(request: CreateCompanyRequest): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>("/companies", request);
  return data;
}

export async function updateCompany(
  companyId: string,
  request: UpdateCompanyRequest
): Promise<CommandResponse> {
  const { data } = await API.patch<CommandResponse>(`/companies/${companyId}`, request);
  return data;
}

export async function archiveCompany(
  companyId: string,
  reason?: string
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/archive`, {
    reason,
  });
  return data;
}

export async function restoreCompany(companyId: string): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/restore`);
  return data;
}

export interface DeleteCompanyOptions {
  cascade?: boolean;          // If true, cascade delete chats/telegram (default: true)
  preserveCompany?: boolean;  // If true, keep company for future re-linking (default: false)
}

export async function deleteCompany(
  companyId: string,
  options: DeleteCompanyOptions = {}
): Promise<CommandResponse> {
  const { cascade = true, preserveCompany = false } = options;
  const { data } = await API.delete<CommandResponse>(`/companies/${companyId}`, {
    params: { cascade, preserve_company: preserveCompany },
  });
  return data;
}

export async function searchCompanies(
  searchTerm: string,
  limit: number = 20
): Promise<CompanySummary[]> {
  const { data } = await API.get<CompanySummary[]>("/companies/search", {
    params: { q: searchTerm, limit },
  });
  return data;
}

export async function getCompanyByVat(vat: string): Promise<CompanyDetail | null> {
  const { data } = await API.get<CompanyDetail>(`/companies/by-vat/${vat}`);
  return data;
}

// -----------------------------------------------------------------------------
// User's Companies
// -----------------------------------------------------------------------------

export async function getMyCompanies(
  includeArchived: boolean = false,
  limit: number = 50,
  offset: number = 0
): Promise<UserCompanyInfo[]> {
  const { data } = await API.get<UserCompanyInfo[]>("/companies/my", {
    params: {
      include_archived: includeArchived,
      limit,
      offset,
    },
  });
  return data;
}

// -----------------------------------------------------------------------------
// Company Users Management
// -----------------------------------------------------------------------------

export async function getCompanyUsers(
  companyId: string,
  includeInactive: boolean = false
): Promise<CompanyUserInfo[]> {
  const { data } = await API.get<CompanyUserInfo[]>(`/companies/${companyId}/users`, {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function addUserToCompany(
  companyId: string,
  request: AddUserRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/users`, request);
  return data;
}

export async function removeUserFromCompany(
  companyId: string,
  userId: string,
  reason?: string
): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/companies/${companyId}/users/${userId}`, {
    data: { reason },
  });
  return data;
}

export async function changeUserRole(
  companyId: string,
  userId: string,
  request: ChangeUserRoleRequest
): Promise<CommandResponse> {
  const { data } = await API.patch<CommandResponse>(
    `/companies/${companyId}/users/${userId}/role`,
    request
  );
  return data;
}

export async function getUserCompanyRelationship(
  companyId: string,
  userId: string
): Promise<UserCompanyRelationship> {
  const { data } = await API.get<UserCompanyRelationship>(
    `/companies/${companyId}/users/${userId}/relationship`
  );
  return data;
}

// -----------------------------------------------------------------------------
// Telegram Integration
// -----------------------------------------------------------------------------

export async function getCompanyTelegramGroups(
  companyId: string
): Promise<TelegramSupergroupInfo[]> {
  const { data } = await API.get<TelegramSupergroupInfo[]>(`/companies/${companyId}/telegram`);
  return data;
}

export async function createTelegramGroup(
  companyId: string,
  title: string,
  description?: string
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/telegram`, {
    title,
    description,
  });
  return data;
}

export async function linkTelegramGroup(
  companyId: string,
  telegramGroupId: number
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/telegram/link`, {
    telegram_group_id: telegramGroupId,
  });
  return data;
}

export async function unlinkTelegramGroup(
  companyId: string,
  telegramGroupId: number
): Promise<CommandResponse> {
  const { data } = await API.delete<CommandResponse>(`/companies/${companyId}/telegram/link`, {
    data: { telegram_group_id: telegramGroupId },
  });
  return data;
}

// -----------------------------------------------------------------------------
// Balance Operations
// -----------------------------------------------------------------------------

export async function getCompanyBalance(companyId: string): Promise<BalanceInfo> {
  const { data } = await API.get<BalanceInfo>(`/companies/${companyId}/balance`);
  return data;
}

export async function getBalanceHistory(
  companyId: string,
  limit: number = 50,
  offset: number = 0
): Promise<BalanceTransaction[]> {
  const { data } = await API.get<BalanceTransaction[]>(`/companies/${companyId}/balance/history`, {
    params: { limit, offset },
  });
  return data;
}

export async function updateCompanyBalance(
  companyId: string,
  request: UpdateBalanceRequest
): Promise<CommandResponse> {
  const { data } = await API.post<CommandResponse>(`/companies/${companyId}/balance`, request);
  return data;
}

// -----------------------------------------------------------------------------
// Logo Operations
// -----------------------------------------------------------------------------

export interface LogoUploadResponse {
  success: boolean;
  logo_url?: string;
  error?: string;
}

export interface LogoDeleteResponse {
  success: boolean;
  error?: string;
}

export async function uploadCompanyLogo(
  companyId: string,
  file: File
): Promise<LogoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await API.post<LogoUploadResponse>(
    `/companies/${companyId}/logo`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return data;
}

export async function deleteCompanyLogo(
  companyId: string,
  logoUrl: string
): Promise<LogoDeleteResponse> {
  const { data } = await API.delete<LogoDeleteResponse>(`/companies/${companyId}/logo`, {
    params: { logo_url: logoUrl },
  });
  return data;
}
