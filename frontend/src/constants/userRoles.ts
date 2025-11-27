import type { Database } from '@/integrations/supabase/types';

export type ChatBusinessRole = Database['public']['Enums']['chat_business_role'];
export type TelegramGroupType = Database['public']['Enums']['telegram_group_type'];

export interface RoleOption {
  value: ChatBusinessRole;
  label: string;
}

export const ROLE_OPTIONS: RoleOption[] = [
  { value: 'client', label: 'Клиент' },
  { value: 'payment_agent', label: 'Плат. агент' },
  { value: 'logistician', label: 'Логист' },
  { value: 'purchasers', label: 'Закупщики' },
  { value: 'unassigned', label: 'Не назначен' },
  { value: 'manager', label: 'Менеджер' },
];

export const DEFAULT_ROLE_BY_GROUP_TYPE: Record<TelegramGroupType, ChatBusinessRole> = {
  client: 'client',
  payments: 'payment_agent',
  logistics: 'logistician',
  buyers: 'purchasers',
  others: 'unassigned',
  wellwon: 'manager',
};

export const mapRoleToLabel = (role: ChatBusinessRole | null): string => {
  if (!role) return 'Не назначен';
  const option = ROLE_OPTIONS.find(opt => opt.value === role);
  return option?.label || 'Не назначен';
};

export const mapGroupTypeToDefaultRole = (groupType: TelegramGroupType): ChatBusinessRole => {
  return DEFAULT_ROLE_BY_GROUP_TYPE[groupType] || 'unassigned';
};