# 📊 WellWon App - Детальный Архитектурный Отчёт

**Дата анализа:** 2025-11-17
**Версия:** Frontend Old + Supabase Backend

---

## 🎯 Общий Обзор

**WellWon App** - это B2B платформа для чатов и коммуникаций с интеграцией Telegram, построенная на современном стеке: **React + TypeScript + Supabase**.

---

## 🛠 FRONTEND АРХИТЕКТУРА

### **Технологический Стек**

#### **Основа:**
- **React 18.3.1** - UI библиотека
- **TypeScript 5.5.3** - типизация
- **Vite 5.4.1** - сборщик (fast HMR)
- **React Router DOM 6.26.2** - маршрутизация

#### **UI Framework:**
- **Radix UI** - 20+ компонентов (dialog, dropdown, popover, tabs, etc.)
- **Tailwind CSS 3.4.11** - стилизация
- **shadcn/ui** - готовые компоненты поверх Radix
- **Lucide React** - иконки
- **class-variance-authority** - вариативные стили

#### **State Management & Data Fetching:**
- **TanStack Query (React Query) 5.56.2** - серверное состояние, кэширование
- **React Context API** - глобальное состояние (Auth, Platform, Chat, etc.)
- **React Hook Form 7.53.0** - формы
- **@hookform/resolvers** - валидация форм

#### **Backend Integration:**
- **@supabase/supabase-js 2.52.0** - клиент Supabase
  - Realtime subscriptions
  - Auth
  - Database queries
  - Storage

#### **Дополнительные Библиотеки:**
- **date-fns** - работа с датами
- **recharts** - графики/charts
- **qrcode** - генерация QR кодов
- **use-sound** - звуковые уведомления
- **embla-carousel-react** - карусели
- **react-resizable-panels** - ресайзабельные панели
- **vaul** - drawer компонент

---

### **Структура Проекта**

```
src/
├── components/        # UI компоненты
│   ├── auth/         # Авторизация
│   ├── shared/       # Общие компоненты
│   └── ui/           # shadcn/ui компоненты
├── contexts/         # React Context провайдеры
│   ├── AuthContext          # Аутентификация
│   ├── PlatformContext      # Платформа/компания
│   ├── RealtimeChatContext  # Realtime чат
│   ├── ProfileModalContext  # Модалки профиля
│   └── chat/                # Чат контексты
├── pages/            # Страницы (роуты)
│   ├── HomePage
│   ├── PlatformPage        # Основная платформа с чатами
│   ├── Version3           # Financing page
│   ├── AuthPage
│   └── Legal pages (Terms, Privacy, Cookie)
├── hooks/            # Custom React hooks
│   ├── useRealtimeChat    # Realtime чат логика
│   ├── useMessageTemplates
│   ├── useMentions
│   ├── useAppRecovery
│   └── useNotificationSound
├── services/         # Бизнес-логика/API
│   ├── RealtimeChatService
│   ├── TelegramChatService
│   ├── CompanyService
│   ├── CompanyLogoService
│   └── MessageTemplateService
├── utils/            # Утилиты
│   ├── cacheManager         # Кэш менеджер
│   ├── performanceMonitor   # Мониторинг производительности
│   ├── logger               # Логирование
│   ├── telegramUtils
│   └── chat utils
├── types/            # TypeScript типы
├── integrations/
│   └── supabase/    # Supabase client & types
├── constants/        # Константы
└── styles/           # Дополнительные стили
```

---

### **Роутинг (React Router v6)**

```typescript
/ - HomePage (лендинг)
/financing - Version3 (страница финансирования)
/auth - AuthPage (авторизация)
/platform/:section?/:chatId? - PlatformPage (защищенный роут)
/design - DesignPage
/terms, /privacy, /cookie-policy - Legal pages
* - NotFound (404)
```

**Защита роутов:** `ProtectedRoute` компонент проверяет аутентификацию

---

### **State Management Паттерн**

1. **React Context** для глобального состояния:
   - `AuthContext` - пользователь, сессия
   - `PlatformContext` - выбранная компания
   - `RealtimeChatContext` - состояние чатов
   - `ProfileModalContext` - модалки профиля

2. **TanStack Query** для серверных данных:
   - Автоматический кэш (5 мин staleTime)
   - Refetch on window focus отключен
   - Оптимизация запросов

3. **Custom Hooks** для бизнес-логики:
   - `useRealtimeChat` - управление чатами
   - `useMessageTemplates` - шаблоны сообщений
   - `useMentions` - упоминания пользователей

---

### **Оптимизация Производительности**

1. **Lazy Loading:**
   - Все страницы загружаются асинхронно через `React.lazy()`
   - Custom `createLazyComponent` с error boundaries

2. **Кэширование:**
   - `cacheManager` - автоматическая очистка устаревшего кэша
   - `performanceMonitor` - отслеживание метрик
   - `performanceTracker` - custom метрики

3. **Error Recovery:**
   - `ErrorBoundary` компонент
   - `useAppRecovery` hook для восстановления

4. **Logging System:**
   - Custom `logger` с метаданными
   - Логирование user actions, errors, info

---

## 💾 BACKEND АРХИТЕКТУРА (Supabase)

### **Database Schema (PostgreSQL)**

#### **Основные Таблицы:**

**1. Пользователи & Профили:**
```sql
profiles
├── id (uuid, PK)
├── user_id (uuid, FK → auth.users)
├── display_name, first_name, last_name
├── avatar_url, bio
├── type (user role: ww_admin, ww_manager, entrepreneur, investor, etc.)
└── created_at, updated_at
```

**2. Компании:**
```sql
companies
├── id (uuid, PK)
├── name, description
├── logo_url
├── owner_id (uuid, FK → auth.users)
└── metadata (jsonb)

user_companies (многие-ко-многим)
├── user_id, company_id
└── role (owner, admin, member)
```

**3. Чаты (Realtime):**
```sql
chats
├── id (uuid, PK)
├── name
├── type (direct | group | company)
├── company_id (опционально)
├── created_by
└── metadata (jsonb)

chat_participants
├── chat_id, user_id
├── role (member | admin | observer)
├── last_read_at
└── is_active

messages
├── id (uuid, PK)
├── chat_id, sender_id
├── content (text)
├── message_type (text | file | voice | image | system)
├── reply_to_id (для ответов)
├── file_url, file_name, file_size, file_type
├── voice_duration
├── is_edited, is_deleted
└── metadata (jsonb)

message_reads
├── message_id, user_id
└── read_at

typing_indicators
├── chat_id, user_id
├── started_at
└── expires_at (TTL 10 seconds)
```

**4. Telegram Integration:**
```sql
tg_users
├── id (uuid, PK)
├── user_id (FK → auth.users)
├── telegram_id (bigint)
├── username, first_name, last_name
└── phone_number

telegram_supergroups
├── id, chat_id
├── title, username
└── member_count

telegram_group_members
├── group_id, telegram_user_id
└── role (admin | member)
```

**5. Дополнительные:**
```sql
message_templates - шаблоны сообщений
currencies - валюты
news - новости
system_logs - логи системы
```

---

### **Row Level Security (RLS) Политики**

**Безопасность на уровне БД:**

1. **Профили:**
   - Все могут читать
   - Пользователь может обновлять только свой профиль

2. **Чаты:**
   - Видны только участникам + админам WellWon
   - Создатель или админ может обновлять

3. **Сообщения:**
   - Видны только участникам чата
   - Отправитель может редактировать/удалять свои сообщения

4. **Компании:**
   - Участники компании видят данные
   - Owner/admin может управлять

**Роли:**
- `ww_admin`, `ww_manager`, `ww_developer` - команда WellWon (полный доступ)
- `entrepreneur`, `investor` - клиенты
- `company_admin`, `company_member` - роли внутри компании

---

### **Edge Functions (Serverless)**

**11 Supabase Edge Functions:**

1. **Telegram Bot API:**
   - `telegram-webhook` - webhook для бота
   - `telegram-send` - отправка сообщений
   - `telegram-verify-topics` - проверка топиков
   - `telegram-file-proxy` - проксирование файлов
   - `telegram-group-create` - создание групп
   - `telegram-health` - health check
   - `telegram-backfill-media` - загрузка медиа

2. **Authentication:**
   - `quick-login` - быстрый вход

3. **Integrations:**
   - `dadata-api-inn` - проверка ИНН через DaData API

4. **Storage:**
   - `storage-make-public` - управление публичными файлами

5. **Shared:**
   - `_shared` - общие утилиты для функций

---

### **Realtime Subscriptions**

**Supabase Realtime используется для:**
- Новые сообщения в чатах
- Typing indicators (кто печатает)
- Message reads (прочитано)
- Chat participants changes
- Online/offline статусы

**Подписки в коде:**
```typescript
supabase
  .channel(`chat:${chatId}`)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'messages'
  }, handleNewMessage)
  .subscribe()
```

---

### **Storage (Supabase Storage)**

**Buckets:**
- Загрузка файлов: документы, изображения, голосовые
- Интеграция с Telegram (telegram-file-proxy)
- Автоматическая обработка прав доступа

---

## 🔐 AUTHENTICATION & AUTHORIZATION

### **Authentication Flow:**

1. **Supabase Auth:**
   - Email/Password
   - Magic Link (возможно)
   - Telegram Login (через quick-login function)

2. **Session Management:**
   - localStorage persistence
   - Auto refresh token
   - AuthContext обертка

3. **User Roles:**
   - Сохраняются в `profiles.type`
   - Проверяются на уровне RLS
   - Используются для UI/UX (показ функций по ролям)

### **Authorization:**
- **Frontend:** Проверка `user.type` в компонентах
- **Backend:** RLS политики + Edge Functions проверки
- **Роли:** ww_admin > ww_manager > ww_developer > entrepreneur/investor

---

## 🔄 DATA FLOW DIAGRAM

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────┐
│  React App (Vite + TypeScript)  │
│  ┌─────────────────────────┐    │
│  │  Components & Pages     │    │
│  └───────────┬─────────────┘    │
│              ↓                   │
│  ┌─────────────────────────┐    │
│  │  Contexts & Hooks       │    │
│  └───────────┬─────────────┘    │
│              ↓                   │
│  ┌─────────────────────────┐    │
│  │  Services               │    │
│  └───────────┬─────────────┘    │
│              ↓                   │
│  ┌─────────────────────────┐    │
│  │  Supabase Client        │    │
│  │  - Query                │    │
│  │  - Realtime             │    │
│  │  - Auth                 │    │
│  └───────────┬─────────────┘    │
└──────────────┼──────────────────┘
               │
               ↓
     ┌─────────────────────┐
     │    Supabase Cloud   │
     │  ┌───────────────┐  │
     │  │  PostgreSQL   │  │
     │  │  + RLS        │  │
     │  └───────────────┘  │
     │  ┌───────────────┐  │
     │  │  Realtime     │  │
     │  └───────────────┘  │
     │  ┌───────────────┐  │
     │  │  Edge Funcs   │◄─┼── Telegram Bot API
     │  └───────────────┘  │◄─┼── DaData API
     │  ┌───────────────┐  │
     │  │  Storage      │  │
     │  └───────────────┘  │
     └─────────────────────┘
```

---

## 📱 КЛЮЧЕВЫЕ ФИЧИ ПРИЛОЖЕНИЯ

### **1. Realtime Chat System**
- Групповые и личные чаты
- Ответы на сообщения (reply_to_id)
- Typing indicators
- Message reads
- Голосовые сообщения
- Файлы и изображения
- Упоминания (@mentions)
- Шаблоны сообщений

### **2. Telegram Integration**
- Двусторонняя синхронизация
- Telegram Bot
- Создание супергрупп
- Проксирование файлов
- Backfill медиа

### **3. Company Management**
- Создание компаний
- Управление участниками
- Роли внутри компании
- Чаты компании

### **4. User Profiles**
- Редактирование профиля
- Avatar upload
- Роли пользователей

### **5. Authentication**
- Email/password
- Telegram login
- Session management

---

## 🎨 UI/UX ПАТТЕРНЫ

### **Design System:**
- Использует **Radix UI primitives**
- Кастомизация через **Tailwind**
- Темная/светлая тема (возможна)
- Адаптивный дизайн

### **Notifications:**
- Toast уведомления (`@/components/ui/toaster`)
- Звуковые уведомления (`use-sound`)
- Browser notifications (возможно)

### **Loading States:**
- Skeleton loaders
- PageLoader для lazy routes
- Suspense boundaries

---

## 🚀 DEPLOYMENT & BUILD

### **Build Configuration:**
```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "build:dev": "vite build --mode development",
  "preview": "vite preview"
}
```

### **Environment:**
- Supabase URL: `qqhuwvveovmfyihjnanx.supabase.co`
- Supabase Project: WellWon App
- Region: EU North 1 (Stockholm)
- Database: PostgreSQL через Supabase

---

## 📊 TECH DECISIONS & BEST PRACTICES

### **✅ Что сделано хорошо:**

1. **TypeScript** - полная типизация
2. **Модульная архитектура** - разделение на contexts, hooks, services
3. **RLS Security** - безопасность на уровне БД
4. **Performance Optimization** - lazy loading, cache, monitoring
5. **Error Handling** - error boundaries, app recovery
6. **Realtime** - эффективное использование Supabase Realtime
7. **Scalable DB Schema** - нормализованная схема с индексами

### **⚠️ Потенциальные улучшения:**

1. **State Management** - можно рассмотреть Zustand вместо множества Context
2. **Testing** - отсутствуют тесты (нет jest/vitest в devDeps)
3. **Монолитный PlatformPage** - может потребовать разбиения
4. **Telegram integration** - сложная логика в Edge Functions

---

## 📈 МАСШТАБИРОВАНИЕ

### **Текущая архитектура позволяет:**
- **Горизонтальное масштабирование** - Supabase автоматически
- **Realtime** - до 100K одновременных подключений
- **Edge Functions** - serverless, автоscaling
- **CDN** - статика через Vite build

### **Ограничения:**
- Supabase Free tier лимиты
- RLS может быть узким местом при сложных запросах
- Realtime subscriptions - лимит на количество каналов

---

## 🎯 ВЫВОДЫ

**WellWon App** - современное SPA приложение с продуманной архитектурой:

- **Frontend:** React 18 + TypeScript + Vite + современный стек UI
- **Backend:** Supabase (PostgreSQL + Realtime + Edge Functions)
- **Security:** RLS + TypeScript + валидация
- **Performance:** Оптимизации, кэширование, lazy loading
- **Features:** Realtime чаты + Telegram + компании + роли

**Стек идеально подходит для B2B SaaS с realtime коммуникациями.**

---

## 📁 СТРУКТУРА REFERENCE

```
reference/
├── docs/
│   └── ARCHITECTURE_REPORT.md  # Этот документ
├── frontend_old/               # Старый фронтенд для референса
│   ├── src/                    # Исходный код
│   ├── package.json            # Зависимости
│   └── supabase/               # Supabase конфигурация (дубликат)
└── supabase/                   # Backend референс
    ├── migrations/             # 160 SQL миграций
    ├── functions/              # 11 Edge Functions
    └── config.toml             # Конфигурация
```

---

**Отчёт составлен:** Claude Code
**Для проекта:** WellWon App Migration
