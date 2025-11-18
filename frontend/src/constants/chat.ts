// Константы для чата
export const CHAT_CONSTANTS = {
  MESSAGE_TYPES: {
    TEXT: 'text',
    IMAGE: 'image',
    FILE: 'file',
    VOICE: 'voice',
    INTERACTIVE: 'interactive',
    SYSTEM: 'system'
  },
  CHAT_TYPES: {
    DIRECT: 'direct',
    GROUP: 'group',
    COMPANY: 'company'
  },
  USER_TYPES: {
    WW_ADMIN: 'ww_admin',
    WW_MANAGER: 'ww_manager',
    WW_DEVELOPER: 'ww_developer'
  },
  PARTICIPANT_ROLES: {
    ADMIN: 'admin',
    MODERATOR: 'moderator',
    MEMBER: 'member',
    OBSERVER: 'observer'
  }
} as const;

export const USER_TYPE_LABELS = {
  [CHAT_CONSTANTS.USER_TYPES.WW_ADMIN]: 'Админ',
  [CHAT_CONSTANTS.USER_TYPES.WW_MANAGER]: 'Админ', 
  [CHAT_CONSTANTS.USER_TYPES.WW_DEVELOPER]: 'Админ'
} as const;

export const ROLE_LABELS = {
  [CHAT_CONSTANTS.PARTICIPANT_ROLES.ADMIN]: 'Администратор',
  [CHAT_CONSTANTS.PARTICIPANT_ROLES.MODERATOR]: 'Модератор',
  [CHAT_CONSTANTS.PARTICIPANT_ROLES.MEMBER]: 'Участник',
  [CHAT_CONSTANTS.PARTICIPANT_ROLES.OBSERVER]: 'Наблюдатель'
} as const;