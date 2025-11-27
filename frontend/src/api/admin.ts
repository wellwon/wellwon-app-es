// =============================================================================
// File: src/api/admin.ts — Admin API endpoints
// =============================================================================

import { API } from './core';

// =============================================================================
// Types
// =============================================================================

export interface AdminUser {
  id: string;
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  active: boolean;
  developer: boolean;
  created_at: string;
}

export interface AdminUserUpdate {
  active?: boolean;
  developer?: boolean;
}

// =============================================================================
// Admin API
// =============================================================================

export const adminApi = {
  /**
   * Get all users for admin management
   */
  getUsers: (params?: { includeInactive?: boolean; limit?: number; offset?: number }) =>
    API.get<AdminUser[]>('/admin/users', { params }),

  /**
   * Update user status (active/developer)
   */
  updateUser: (userId: string, data: AdminUserUpdate) =>
    API.patch<AdminUser>(`/admin/users/${userId}`, data),
};
