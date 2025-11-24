# Декларант AI - Модуль декларирования ФТС 3.0

Полностью изолированное standalone приложение для управления пакетной обработкой деклараций ФТС в рамках платформы WellWon.

## Структура модуля

```
frontend/src/pages/declarant/
├── DeclarantPage.tsx    # Главный компонент страницы
├── index.ts             # Экспорты модуля
└── README.md            # Документация
```

## Доступ

Модуль доступен по маршруту: **`/declarant`**

URL: http://localhost:5174/declarant

## Особенности

- **Полностью изолирован** от остальной платформы
- **Standalone layout** - собственный sidebar и header
- **Темная/светлая тема** - переключатель встроен в интерфейс
- **Responsive дизайн** - адаптивная верстка под разные экраны
- **Защищенный доступ** - требуется авторизация (ProtectedRoute)

## Текущее состояние

**Версия:** 0.1 (Mock UI)

Сейчас модуль работает только с mock-данными и не имеет функционала. Это чистый UI/дизайн для визуализации.

### Компоненты:

1. **SidebarMock** - боковое меню навигации (всегда темная тема)
2. **HeaderBarMock** - верхняя панель с breadcrumbs и переключателем темы
3. **DeclarantPage** - основная страница со статистикой и таблицей

### Mock данные:

- **mockStats** - статистика пакетов (всего 6, завершено 5)
- **mockBatches** - таблица деклараций (6 записей FTS-00099 до FTS-00104)

## Оптимизации

Код был оптимизирован для производительности:

- `React.memo` для SidebarMock и HeaderBarMock
- Константа NAVIGATION_SECTIONS вынесена из компонента
- Оптимизирована работа с темами в таблице (без split в render)
- Удалены лишние импорты

## Roadmap

### Фаза 1: Backend интеграция (Будущее)

Когда потребуется функционал, нужно будет создать:

**Backend домен:** `app/ww_declarant/`
- `aggregate.py` - DeclarantBatchAggregate
- `commands.py` - CreateBatchCommand, ProcessDocumentCommand, etc.
- `events.py` - BatchCreatedEvent, DocumentProcessedEvent, etc.
- `projectors.py` - Проекции в PostgreSQL
- `read_models.py` - Схемы read моделей
- `queries.py` - GetBatchesQuery, GetBatchDetailsQuery, etc.
- `command_handlers/` - Обработчики команд
- `query_handlers/` - Обработчики запросов

**API Router:** `app/api/routers/declarant_router.py`
- POST /declarant/batches - создать пакет
- GET /declarant/batches - получить список
- GET /declarant/batches/{id} - детали пакета
- POST /declarant/batches/{id}/documents - добавить документы
- GET /declarant/stats - статистика

### Фаза 2: AI интеграция
- Подключение модели AI для обработки деклараций
- Автоматическое извлечение данных из документов
- Валидация и проверка соответствия ФТС

### Фаза 3: Реальный функционал
- Загрузка документов
- Обработка в реальном времени
- Экспорт в различные форматы
- История изменений
- Уведомления и алерты

## Архитектура

Модуль следует CQRS + Event Sourcing паттерну WellWon:

```
Write Side:  API → Command → CommandBus → Aggregate → Event → EventStore
Read Side:   API → Query → QueryBus → PostgreSQL → ReadModel
Event Flow:  EventStore → EventBus → Projector → PostgreSQL
```

## Технологии

- **React 19.2** + TypeScript
- **Vite** для сборки
- **TailwindCSS** для стилей
- **Lucide React** для иконок
- **shadcn/ui** компоненты (Checkbox, Avatar, Badge)
- **React Router** для роутинга

## Разработка

```bash
# Установить зависимости
cd frontend
npm install

# Запустить dev server
npm run dev

# Сборка
npm run build
```

## Контакты

По вопросам модуля обращаться к команде разработки WellWon.
