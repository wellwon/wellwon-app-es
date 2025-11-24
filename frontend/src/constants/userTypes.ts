// User Types - в соответствии с ENUM в базе данных
// Синхронизировано с PostgreSQL user_type_enum

export const USER_TYPES = {
  CLIENT: 'client',
  PAYMENT_AGENT: 'payment_agent',
  LOGISTICIAN: 'logistician',
  PURCHASER: 'purchaser',
  UNASSIGNED: 'unassigned',
  MANAGER: 'manager',
} as const;

export type UserType = typeof USER_TYPES[keyof typeof USER_TYPES];

export interface UserTypeOption {
  value: UserType;
  label: string;
  description?: string;
}

export const USER_TYPE_OPTIONS: UserTypeOption[] = [
  {
    value: USER_TYPES.CLIENT,
    label: 'Клиент',
    description: 'Клиент компании'
  },
  {
    value: USER_TYPES.PAYMENT_AGENT,
    label: 'Плат. агент',
    description: 'Платёжный агент'
  },
  {
    value: USER_TYPES.LOGISTICIAN,
    label: 'Логист',
    description: 'Специалист по логистике'
  },
  {
    value: USER_TYPES.PURCHASER,
    label: 'Закупщик',
    description: 'Специалист по закупкам'
  },
  {
    value: USER_TYPES.UNASSIGNED,
    label: 'Не назначен',
    description: 'Роль не назначена'
  },
  {
    value: USER_TYPES.MANAGER,
    label: 'Менеджер',
    description: 'Менеджер компании'
  },
];

export const USER_TYPE_LABELS: Record<UserType, string> = {
  [USER_TYPES.CLIENT]: 'Клиент',
  [USER_TYPES.PAYMENT_AGENT]: 'Плат. агент',
  [USER_TYPES.LOGISTICIAN]: 'Логист',
  [USER_TYPES.PURCHASER]: 'Закупщик',
  [USER_TYPES.UNASSIGNED]: 'Не назначен',
  [USER_TYPES.MANAGER]: 'Менеджер',
};

export function getUserTypeLabel(userType: string | undefined): string {
  if (!userType) return 'Пользователь';
  return USER_TYPE_LABELS[userType as UserType] || 'Пользователь';
}
