# Документация API Kontur.Deklarant

**Версии API:**
- PAO API v1 (OAS 3.0)
- NAG API v1 (OAS 3.0)
- API справочников v1 (OAS 3.0)
- Common API v1 (OAS 3.0)

**Базовый URL:** `https://api-d.kontur.ru`

> **Примечание:** Тестовой площадки нет. Для тестирования используется тестовый API-ключ на production URL.

**Аутентификация:**
- Заголовок: `X-Kontur-ApiKey` (required) - API ключ для доступа к системе
- SessionID (sid): Получается через `POST /auth/v1/authenticate`
- Формат авторизации: SessionID передается в заголовке `Authorization` для всех запросов

**Пример получения SessionID:**
```bash
curl -X POST 'https://api-d.kontur.ru/auth/v1/authenticate?login=your_email%40example.com&pass=your_password' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

## Переменные окружения

Для работы с API рекомендуется хранить учетные данные в переменных окружения:

```bash
# .env файл
# =============================================================================
# KONTUR DECLARANT API (External Service Integration)
# =============================================================================

# API Endpoint (единственный URL, тестовой площадки нет)
KONTUR_API_BASE_URL=https://api-d.kontur.ru

# Authentication Credentials (TEST - REPLACE IN PRODUCTION)
KONTUR_API_LOGIN=etoai@comfythings.com
KONTUR_API_PASSWORD=etoaicomfythingscom
KONTUR_API_KEY=84f53197-e8c0-70b8-f608-e45080b06eeb

# Session ID (obtained via /auth/v1/authenticate, refresh when expired)
# Note: SID has limited lifetime, backend should refresh automatically
KONTUR_API_SID=407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA
```

**Использование в коде:**
```python
import os
from urllib.parse import quote

KONTUR_BASE_URL = os.getenv("KONTUR_API_BASE_URL", "https://api-d.kontur.ru")
KONTUR_LOGIN = os.getenv("KONTUR_API_LOGIN")
KONTUR_PASSWORD = os.getenv("KONTUR_API_PASSWORD")
KONTUR_API_KEY = os.getenv("KONTUR_API_KEY")
KONTUR_SID = os.getenv("KONTUR_API_SID")

# URL-encode login for query parameter
encoded_login = quote(KONTUR_LOGIN, safe='')

# Authenticate
auth_url = f"{KONTUR_BASE_URL}/auth/v1/authenticate?login={encoded_login}&pass={KONTUR_PASSWORD}"
```

---

## О продукте

Контур.Декларант — это сервис для создания документов и обмена электронными стандартизированными сообщениями между декларантами и ФТС.

**Основные возможности:**
- Создание и управление таможенными декларациями
- Работа с документооборотом
- Расчет таможенных платежей
- Получение справочной информации по ТНВЭД
- Печать документов в различных форматах

**API доступен по адресу:** `https://api-d.kontur.ru`

---

## Содержание

1. [Обзор функциональности](#обзор-функциональности)
2. [Основные концепции](#основные-концепции)
3. [Схема авторизации и аутентификации](#схема-авторизации-и-аутентификации)
4. [Справочники значений](#справочники-значений)
5. [PAO API - МЧД](#1-pao-api---работа-с-мчд-международная-почтовая-декларация)
6. [NAG API - Документооборот деклараций](#2-nag-api---работа-с-документооборотом-деклараций)
7. [API справочников - ТНВЭД](#3-api-справочников---работа-с-тнвэд)
8. [Common API - Общие методы](#4-common-api---общие-методы)
   - 8.1 [Аутентификация](#41-аутентификация)
   - 8.2 [Работа с документооборотом](#42-работа-с-документооборотом)
   - 8.3 [Работа с документами](#43-работа-с-документами)
   - 8.4 [Печать документов](#44-печать-документов)
   - 8.5 [Работа с контрагентами](#45-работа-с-контрагентами)
9. [Options API - Справочники](#6-options-api---справочники)
10. [JsonTemplates API - Шаблоны](#7-jsontemplates-api---шаблоны)
11. [VehiclePayments API - Платежи при ввозе автомобиля](#8-vehiclepayments-api---платежи-при-ввозе-автомобиля)
12. [Схемы данных (Data Models)](#схемы-данных-data-models)
13. [Примеры использования](#примеры-использования)
14. [Коды ошибок](#коды-ошибок)
15. [Примечания](#примечания)
16. [Контакты](#контакты)

---

## Quick Start - Быстрый старт

### Шаг 1: Получение API ключа

Свяжитесь с Контур.Декларант для получения API ключа и учетных данных.

### Шаг 2: Аутентификация

Выполните запрос для получения SessionID (sid):

```bash
curl -X POST 'https://api-d.kontur.ru/auth/v1/authenticate?login=your_email%40example.com&pass=your_password' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

**Пример с реальными данными:**
```bash
curl -X POST 'https://api-d.kontur.ru/auth/v1/authenticate?login=etoai%40comfythings.com&pass=etoaicomfythingscom' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb'
```

**Ответ (SessionID):**
```
407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA
```

Сохраните полученный SessionID (sid) - он потребуется для всех последующих запросов в заголовке `Authorization`.

### Шаг 3: Создание документооборота

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 0,
    "procedure": 0,
    "singularity": 0,
    "customsId": "YOUR_CUSTOMS_ID",
    "employeeId": "YOUR_EMPLOYEE_ID",
    "name": "Моя первая декларация"
  }'
```

### Шаг 4: Получение информации по коду ТНВЭД

```bash
curl -X GET "https://api-d.kontur.ru/references/v1/tnved/info?tnvedCode=0101210000&dateTime=2025-11-30" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY"
```

### Шаг 5: Расчёт платежей

```bash
curl -X POST "https://api-d.kontur.ru/references/v1/tnved/calculate" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tnved": "0101210000",
    "date": "2025-11-30T12:00:00Z",
    "country": "CN",
    "price": 1000,
    "quantity1": 10,
    "quantity2": 50,
    "quantity3": 0
  }'
```

---

## Обзор функциональности

### PAO API - Международные почтовые декларации (МЧД)
Работа с международными почтовыми декларациями: регистрация и получение информации о заявках.

### NAG API - Документооборот деклараций
Создание и управление документооборотом деклараций на границе РФ.

### API справочников - Справочные данные
Работа с кодами ТНВЭД: получение информации, ставок, расчёт платежей, дополнительные единицы измерения.

### Common API - Общие методы
Универсальный API для работы с:
- Аутентификацией и авторизацией
- Документооборотом всех типов
- Документами и формами
- Контрагентами и организациями
- Печатью документов (HTML/PDF)
- Калькулятором расходов

---

## Основные концепции

**Документооборот (ДО)** — совокупность документов и сообщений, обмен которыми с ФТС относящимся к одной таможенной процедуре. Например, документооборот по процедуре импорт 40 будет содержать документы, относящиеся к графе 54 ДТ.

**Организация** — юридическое лицо или индивидуальный предприниматель, участвующий в электронном документообороте. Когда этот термин используется без уточнения, то это организация, оформляющая ДО в ФТС. Организация получает транспортные реквизиты для работы с транспортом ФТС.

**Сотрудник** — человек с организации и обладает правами подписи и отправки документов. Именно он передаётся в графе 54 ДТ.

**Документ** — это набор реквизитов, необходимых для заполнения графы 44, а также, если у документа есть содержимое, то идентификатор этого содержимого.

**Форма документа** — содержимое документа, с которым работают методы для заполнения документов.

---

## Схема авторизации и аутентификации

### Двухэтапная авторизация

API Kontur.Deklarant использует двухэтапную схему авторизации:

**Этап 1: Получение API ключа**
- Получите API ключ (`X-Kontur-ApiKey`) у службы поддержки Kontur.Deklarant
- Этот ключ используется для всех запросов к API
- Пример: `84f53197-e8c0-70b8-f608-e45080b06eeb`

**Этап 2: Получение SessionID**
- Выполните запрос аутентификации с логином и паролем
- Endpoint: `POST https://api-d.kontur.ru/auth/v1/authenticate?login={email}&pass={password}`
- В заголовке передайте `X-Kontur-ApiKey`
- В ответ получите SessionID (sid) - 64-символьную hex-строку
- Пример sid: `407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA`

### Использование авторизации

**Для всех последующих запросов к API необходимо передавать:**

1. **Заголовок X-Kontur-ApiKey** - ваш API ключ
2. **Заголовок Authorization** - полученный SessionID (sid)

**Пример авторизованного запроса:**
```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/docflows' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb' \
  -H 'Authorization: 407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA'
```

### Важные замечания

- **URL-кодирование:** Email в параметре `login` должен быть URL-кодирован (@ → %40)
- **Формат параметров:** `login` и `pass` передаются как query parameters в URL
- **Разделители параметров:** Используйте `?` для первого параметра и `&` для последующих
- **Время жизни SessionID:** SessionID имеет ограниченный срок действия, при истечении необходимо получить новый
- **Безопасность:** Храните API ключ и SessionID в безопасном месте, не передавайте третьим лицам

### Формат URL аутентификации

**Правильный формат:**
```
https://api-d.kontur.ru/auth/v1/authenticate?login=etoai%40comfythings.com&pass=etoaicomfythingscom
```

**Разбор URL:**
- Base: `https://api-d.kontur.ru/auth/v1/authenticate`
- Query params:
  - `login` = `etoai@comfythings.com` (URL-encoded: `etoai%40comfythings.com`)
  - `pass` = `etoaicomfythingscom`

**Распространённые ошибки:**
```
# НЕПРАВИЛЬНО - без разделителей ? и &
https://api-d.kontur.ru/auth/v1/authenticate?login=etoaix40comfythings.confpass=etoaicomfythingscom

# ПРАВИЛЬНО
https://api-d.kontur.ru/auth/v1/authenticate?login=etoai%40comfythings.com&pass=etoaicomfythingscom
```

### Cookie auth.sid

При работе через браузер SessionID также может храниться в cookie `auth.sid`. Это можно использовать для получения SID через DevTools браузера при отладке в интерфейсе Kontur.Deklarant.

### Рекомендации по интеграции

1. **Автоматическое обновление SID:**
   - Backend должен автоматически обновлять SessionID при получении 401/403 ошибок
   - Хранить SID в кэше (Redis) с TTL меньше времени жизни сессии
   - Реализовать retry-логику с переаутентификацией

2. **Обработка ошибок:**
   - 401 Unauthorized → Переаутентификация
   - 403 Forbidden → Проверить права доступа или API ключ
   - 400 Bad Request → Проверить формат запроса и параметры

3. **Rate limiting:**
   - Использовать очередь запросов для предотвращения превышения лимитов
   - Кэшировать справочные данные (ТНВЭД, организации)

---

## Справочники значений

### Типы организаций (type)
- `0` - Юридическое лицо
- `1` - Индивидуальный предприниматель (ИП)
- `2` - Физическое лицо

### Распределение расходов (distributeBy)
- `1` - По весу брутто
- `2` - По цене
- `3` - Поровну

### Включение расходов (includeIn)
- `1` - В цену
- `2` - В таможенную стоимость
- `3` - В статистическую стоимость

### Типы документооборота
- ИМ (Импорт) - Выпуск для внутреннего потребления
- ЭК (Экспорт)
- ПИ (Предварительное информирование)
- ОЭЗ (Особая экономическая зона)
- ДТ (Декларация на товары)

### Таможенные процедуры
- `40` - Выпуск для внутреннего потребления
- `10` - Экспорт

---

## 1. PAO API - Работа с МЧД (Международная почтовая декларация)

### 1.1 Регистрация МЧД

**Endpoint:** `POST /pao/v1/registeration`

**Описание:** Регистрация МЧД

**Headers:**
- `X-Kontur-ApiKey` - API ключ доступа (обязательный)

**Responses:**
- `200 OK` - Успешная регистрация

---

### 1.2 Получение информации о заявке на регистрацию МЧД

**Endpoint:** `GET /pao/v1/registeration/{registrationId}`

**Описание:** Информация о заявке на регистрацию МЧД

**Path Parameters:**
- `registrationId` (string, required) - ID регистрации

**Headers:**
- `X-Kontur-ApiKey` - API ключ доступа (обязательный)

**Responses:**
- `200 OK` - Успешный ответ

---

## 2. NAG API - Работа с документооборотом деклараций

### 2.1 Создание документооборота

**Endpoint:** `POST /nag/v1/declaration`

**Описание:** Создание документооборота

**Headers:**
- `X-Kontur-ApiKey` - API ключ доступа (обязательный)

**Request Body:** `CreateDeclarationDTOWrap`
```json
{
  "data": {
    "documentID": "string",
    "goods": [
      // массив товаров
    ]
  }
}
```

**Responses:**
- `200 OK` - Документооборот создан

---

### 2.2 Получение информации по документообороту

**Endpoint:** `GET /nag/v1/declaration/{id}`

**Описание:** Информация по документообороту

**Path Parameters:**
- `id` (string, required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` - API ключ доступа (обязательный)

**Responses:**
- `200 OK` - Успешный ответ

---

## 3. API справочников - Работа с ТНВЭД

### 3.1 Получение справочной информации по коду ТНВЭД

**Endpoint:** `GET /references/v1/tnved/info`

**Описание:** Справочная информация по коду товарной номенклатуры внешнеэкономической деятельности

**Query Parameters:**
- `tnvedCode` (string, query) - Код ТНВЭД
- `dateTime` (string($date), query) - Дата и время

**Headers:**
- `X-Kontur-ApiKey` (required) - Ключ доступа к API (ApiKey)

**Responses:**
- `200 OK` - Успешный ответ

**Response Example:**
```json
{
  "heading": "string",
  "references": [
    {
      "name": "string",
      "description": ["string"],
      "federalLaw": "string",
      "linkName": "string",
      "cut": ["string"],
      "heading": "string",
      "inImport": true,
      "inExport": true
    }
  ]
}
```

---

### 3.2 Получение ставок по коду ТНВЭД

**Endpoint:** `GET /references/v1/tnved/rates`

**Описание:** Получение информации о ставках таможенных пошлин

**Query Parameters:**
- `tnvedCode` (string, query) - Код ТНВЭД
- `dateTime` (string($date), query) - Дата и время

**Headers:**
- `X-Kontur-ApiKey` (required) - Ключ доступа к API (ApiKey)

**Responses:**
- `200 OK` - Список ставок

**Response Example:**
```json
{
  "importRates": [
    {
      "id": "string",
      "rateName": "string",
      "goodName": "string",
      "country": "string",
      "rates": [
        {
          "rate": "string",
          "descriptions": [
            {
              "texts": ["string"],
              "lawInfo": {
                "plainName": "string",
                "lawNumber": "string",
                "reference": "string"
              }
            }
          ],
          "info": "string",
          "country": "string",
          "value": 0,
          "isSalePrice": true,
          "notAllFromThisCode": true,
          "allowMerge": true
        }
      ],
      "hint": "string",
      "countryDependent": true,
      "showForceNontedCheckbox": true,
      "value": 0,
      "lawInfo": [
        {
          "plainName": "string",
          "lawNumber": "string",
          "reference": "string"
        }
      ]
    }
  ],
  "exportRates": [
    // аналогичная структура
  ]
}
```

---

### 3.3 Получение дополнительных единиц измерения

**Endpoint:** `POST /references/v1/tnved/calculationUnits`

**Описание:** Метод выводит дополнительные единицы измерения, необходимые для расчёта платежей

**Headers:**
- `X-Kontur-ApiKey` (required) - Ключ доступа к API (ApiKey)

**Request Body:**
```json
{
  "tnved": "string",
  "date": "2025-11-30T16:14:33.439Z",
  "country": "string",
  "price": 0,
  "quantity1": 0,
  "quantity2": 0,
  "quantity3": 0
}
```

**Responses:**
- `200 OK` - Список единиц измерения

**Response Example:**
```json
[
  "string"
]
```

---

### 3.4 Расчёт таможенных платежей

**Endpoint:** `POST /references/v1/tnved/calculate`

**Описание:** Расчёт таможенных платежей по коду ТНВЭД

**Headers:**
- `X-Kontur-ApiKey` (required) - Ключ доступа к API (ApiKey)

**Request Body:**
```json
{
  "tnved": "string",
  "date": "2025-11-30T16:14:33.441Z",
  "country": "string",
  "price": 0,
  "quantity1": 0,
  "quantity2": 0,
  "quantity3": 0
}
```

**Responses:**
- `200 OK` - Результат расчёта

**Response Example:**
```json
{
  "rateId": "string",
  "rateName": "string",
  "rate": "string",
  "descriptions": [
    {
      "texts": ["string"],
      "lawInfo": {
        "plainName": "string",
        "lawNumber": "string",
        "reference": "string"
      }
    }
  ],
  "preferences": {
    "additionalProp1": "string",
    "additionalProp2": "string",
    "additionalProp3": "string"
  },
  "calculationResponseItems": [
    {
      "name": "string",
      "code": "string",
      "price": 0,
      "display": {
        "base": "string",
        "rate": "string",
        "result": "string",
        "specific": "string"
      }
    }
  ],
  "totalPrice": 0
}
```

---

## Схемы данных (Data Models)

### McdDocflowStatus

**Type:** `integer($int32)` (Enum: массив из 6 элементов)

**Описание:** Статус документооборота МЧД

---

### RegistrationStatus

**Описание:** Класс описания состояния заявки на регистрацию

**Свойства:**
- `status` - McdDocflowStatus
- `statusCode` - string
- `statusText` - string
- `resultsByCustoms` - array

---

### ResultByCustoms

**Описание:** Данные полученные от таможни

**Свойства:**
- `resultCode` - string
- `resultDescription` - string

---

### CreateDeclarationDTO

**Свойства:**
- `documentID` - string (ID документа)
- `goods` - array (список товаров)

---

### GoodsDto

**Свойства:**
- `goodsMarking` - string
- `goodsTNVEDCode` - string
- `measureUnitQualifierCode` - string
- `customsCost` - number
- `goodsQuantity` - number
- `originCountryCode` - string

---

### AllRates

**Описание:** Все ставки (импортные и экспортные)

**Свойства:**
- `importRates` - array[MergedRate] (nullable: true)
- `exportRates` - array[MergedRate] (nullable: true)

---

### MergedRate

**Описание:** Объединённая информация о ставке

**Свойства:**
- `id` - string (nullable: true)
- `rateName` - string (nullable: true)
- `goodName` - string (nullable: true)
- `country` - string (nullable: true)
- `rates` - array[RateItem] (nullable: true)
- `hint` - string (nullable: true)
- `countryDependent` - boolean
- `showForceNontedCheckbox` - boolean
- `value` - integer($int32)
- `lawInfo` - array[LawInfo] (nullable: true)

---

### RateItem

**Описание:** Элемент ставки

**Свойства:**
- `rate` - string (nullable: true)
- `descriptions` - array[Description] (nullable: true)
- `info` - string (nullable: true)
- `country` - string (nullable: true)
- `value` - integer($int32)
- `isSalePrice` - boolean
- `notAllFromThisCode` - boolean
- `allowMerge` - boolean

---

### Description

**Описание:** Описание ставки

**Свойства:**
- `texts` - array[string] (nullable: true)
- `lawInfo` - LawInfo

---

### LawInfo

**Описание:** Информация о нормативном документе

**Свойства:**
- `plainName` - string (nullable: true)
- `lawNumber` - string (nullable: true)
- `reference` - string (nullable: true)

---

### DisplayForHuman

**Описание:** Отображение для пользователя

**Свойства:**
- `base` - string (nullable: true)
- `rate` - string (nullable: true)
- `result` - string (nullable: true)
- `specific` - string (nullable: true)

---

### CalculationRequest

**Описание:** Запрос на расчёт платежей

**Свойства:**
- `tnved` - string
- `date` - string
- `country` - string
- `price` - number
- `quantity1` - number
- `quantity2` - number
- `quantity3` - number($double) (nullable: true)

---

### CalculationResponse

**Описание:** Ответ с результатами расчёта

**Свойства:**
- `rateId` - string (nullable: true)
- `rateName` - string (nullable: true)
- `rate` - string (nullable: true)
- `descriptions` - array[Description] (nullable: true)
- `preferences` - object (key-value pairs)
- `calculationResponseItems` - array[CalculationResponseItem] (nullable: true)
- `totalPrice` - number($double)

---

### CalculationResponseItem

**Описание:** Элемент расчёта платежа

**Свойства:**
- `name` - string (nullable: true)
- `code` - string (nullable: true)
- `price` - number($double)
- `display` - DisplayForHuman

---

### Reference

**Описание:** Справочная информация

**Свойства:**
- `name` - string (nullable: true)
- `description` - array[string] (nullable: true)
- `federalLaw` - string (nullable: true)
- `linkName` - string (nullable: true)
- `cut` - array[string] (nullable: true)
- `heading` - string (nullable: true)
- `inImport` - boolean
- `inExport` - boolean

---

### ReferenceGroup

**Описание:** Группа справочной информации

**Свойства:**
- `heading` - string (nullable: true)
- `references` - array[Reference] (nullable: true)

---

### CommonOrg

**Описание:** Структура контрагента

**Свойства:**
- `orgName` - string (nullable: true) - Название организации
- `shortName` - string (nullable: true) - Произвольное название
- `type` - integer - Тип организации (0 - ЮЛ, 1 - ИП, 2 - ФЛ)
- `legalAddress` - Address - Юридический адрес
- `actualAddress` - Address (nullable) - Фактический адрес
- `person` - Person (nullable) - Данные физического лица
- `identityCard` - string (nullable) - Удостоверение личности
- `branchDescription` - string (nullable) - Описание обособленного подразделения
- `inn` - string (nullable) - ИНН
- `kpp` - string (nullable) - КПП
- `ogrn` - string (nullable) - ОГРН
- `okato` - string (nullable) - ОКАТО
- `okpo` - string (nullable) - ОКПО
- `oktmo` - string (nullable) - ОКТМО
- `isForeign` - boolean - Является ли иностранной организацией
- `bankRequisites` - BankRequisites (nullable)

---

### Address

**Описание:** Адрес

**Свойства:**
- `city` - string (nullable: true)
- `settlement` - string (nullable: true)
- `countryName` - string (nullable: true)
- `countryCode` - string (nullable: true)
- `postalCode` - string (nullable: true)
- `region` - string (nullable: true)
- `streetHouse` - string (nullable: true)
- `house` - string (nullable: true)
- `room` - string (nullable: true)

---

### DocflowDto

**Описание:** Данные документооборота

**Свойства:**
- `id` - string($uuid)
- `name` - string (nullable: true)
- `declarationType` - integer
- `procedure` - integer
- `status` - integer
- `statusText` - string (nullable: true)
- `changed` - string($date-time)
- `created` - string($date-time)
- `processId` - string (nullable: true)
- `gtdNumber` - string (nullable: true)
- `inn` - string (nullable: true)
- `kpp` - string (nullable: true)
- `ownName` - string (nullable: true)

---

### DocumentRowDto

**Описание:** Строка документа

**Свойства:**
- `id` - string($uuid)
- `name` - string (nullable: true)
- `declarationType` - integer
- `procedure` - integer
- `status` - integer
- `statusText` - string (nullable: true)
- `changed` - string($date-time)
- `created` - string($date-time)
- `processId` - string (nullable: true)
- `gtdNumber` - string (nullable: true)

---

### DistributionItemDto

**Описание:** Элемент распределения расходов для калькулятора ДТС

**Свойства:**
- `grafa` - string - Вид расхода (номер графы в ДТС: "17", "13A", "11B" и т.д.)
- `distributeBy` - integer - Распределение: 1 - по весу брутто; 2 - по цене; 3 - поровну
- `includeIn` - integer - Включить в: 1 - цену; 2 - таможенную стоимость; 3 - статистическую стоимость
- `currencyCode` - string - Валюта (трехбуквенный код)
- `total` - number($double) - Сумма в валюте
- `borderPlace` - string (nullable: true) - Место прибытия

---

### Message

**Описание:** Сообщение документооборота

**Свойства:**
- `envelopeId` - string (nullable: true)
- `processingDateTime` - string($date-time)
- `preparationDateTime` - string($date-time)
- `messageType` - string (nullable: true)
- `messageDescription` - string (nullable: true)
- `envelope` - string (nullable: true)

---

### DocflowSearchRequest

**Описание:** Запрос поиска документооборота

**Свойства:**
- `query` - string (nullable: true)
- `searchInput` - string (nullable: true)
- `searchedFrom` - string($date-time) (nullable)
- `gtdRegistrationDateTo` - string($date-time) (nullable)
- `createdFrom` - string($date-time) (nullable)
- `createdTo` - string($date-time) (nullable)
- `consignee` - string (nullable: true)
- `sender` - string (nullable: true)
- `documentDateFrom` - string($date-time) (nullable)
- `documentDateTo` - string($date-time) (nullable)
- `presentedDocumentDate` - string($date-time) (nullable)
- `presentedDocumentName` - string (nullable: true)
- `procedure` - integer (nullable)
- `type` - integer (nullable)
- `id` - string($uuid) (nullable)
- `orgIds` - array[string($uuid)] (nullable)
- `includeDeleted` - boolean
- `includeDone` - boolean
- `docflowTags` - array

---

### CreateDocflowRequest

**Описание:** Запрос создания документооборота

**Свойства:**
- `type` - integer - Тип документооборота
- `procedure` - integer - Таможенная процедура
- `singularity` - integer - Особенность
- `customsId` - string($uuid) - Таможенный орган
- `employeeId` - string($uuid) - Идентификатор сотрудника
- `name` - string - Имя документооборота

---

## Примеры использования

**Важно:** Для всех примеров (кроме примера 4 - аутентификация) необходимо передавать два заголовка:
- `X-Kontur-ApiKey` - ваш API ключ
- `Authorization` - SessionID (sid), полученный через `/auth/v1/authenticate`

**Формат авторизованного запроса:**
```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/docflows' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb' \
  -H 'Authorization: 407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA'
```

**Примечание:** В примерах ниже для краткости показан только заголовок `X-Kontur-ApiKey`, но в реальных запросах необходимо также добавлять заголовок `Authorization` с вашим SessionID.

---

### Пример 1: Получение информации по коду ТНВЭД

```bash
curl -X GET "https://api-d.kontur.ru/references/v1/tnved/info?tnvedCode=0101210000&dateTime=2025-11-30" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY"
```

### Пример 2: Расчёт таможенных платежей

```bash
curl -X POST "https://api-d.kontur.ru/references/v1/tnved/calculate" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tnved": "0101210000",
    "date": "2025-11-30T12:00:00Z",
    "country": "CN",
    "price": 1000,
    "quantity1": 10,
    "quantity2": 50,
    "quantity3": 0
  }'
```

### Пример 3: Создание документооборота декларации

```bash
curl -X POST "https://api-d.kontur.ru/nag/v1/declaration" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "documentID": "DOC-2025-001",
      "goods": [
        {
          "goodsMarking": "Product A",
          "goodsTNVEDCode": "0101210000",
          "measureUnitQualifierCode": "166",
          "customsCost": 1000,
          "goodsQuantity": 10,
          "originCountryCode": "CN"
        }
      ]
    }
  }'
```

### Пример 4: Аутентификация и получение SessionID

```bash
# Получение SessionID (sid)
curl -X POST 'https://api-d.kontur.ru/auth/v1/authenticate?login=etoai%40comfythings.com&pass=etoaicomfythingscom' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb'

# Ответ (SessionID):
# 407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA

# Использование полученного sid в других запросах:
curl -X GET 'https://api-d.kontur.ru/common/v1/docflows' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb' \
  -H 'Authorization: 407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA'
```

### Пример 5: Создание документооборота через Common API

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 0,
    "procedure": 0,
    "singularity": 0,
    "customsId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "employeeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Выпуск для внутреннего потребления ИМ 40"
  }'
```

### Пример 6: Получение списка документооборотов

```bash
curl -X GET "https://api-d.kontur.ru/common/v1/docflows?take=1000&status=0" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY"
```

### Пример 7: Поиск документооборота

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows/search?take=50&skip=0" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "string",
    "searchInput": "string",
    "createdFrom": "2025-11-01T00:00:00.000Z",
    "createdTo": "2025-11-30T23:59:59.999Z",
    "procedure": 0,
    "type": 0,
    "includeDeleted": false,
    "includeDone": true
  }'
```

### Пример 8: Создание российской организации

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/commonOrganizations" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 0,
    "isForeign": false,
    "orgName": "ООО \"РОМАШКА\"",
    "shortName": "РОМАШКА",
    "inn": "7719483568",
    "kpp": "111111111",
    "ogrn": "1187746252821",
    "okato": "12341234213",
    "okpo": "12341234213",
    "oktmo": "12341234213",
    "legalAddress": {
      "city": "г. Москва",
      "settlement": "",
      "countryName": "РОССИЯ",
      "countryCode": "RU",
      "postalCode": "105318",
      "region": "Москва",
      "streetHouse": "ул. Мироновская",
      "house": "дом 9",
      "room": "кв. 50"
    }
  }'
```

### Пример 9: Получение организации по ИНН

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/getOrCreateCommonOrgByInn?inn=6663003127" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY"
```

### Пример 10: Создание ДТС с калькулятором расходов

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows/{docflowId}/documents/createDteWithCalculator?dtsType=1" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "grafa": "17",
      "distributeBy": 1,
      "includeIn": 2,
      "borderPlace": "пограничный пункт",
      "currencyCode": "USD",
      "total": 500
    },
    {
      "grafa": "13A",
      "distributeBy": 2,
      "includeIn": 2,
      "borderPlace": "",
      "currencyCode": "USD",
      "total": 500
    }
  ]'
```

### Пример 11: Установка контрагента в график документа

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows/{docflowId}/form/{formId}/setCommonOrg?commonOrgId=3fa85f64-5717-4562-b3fc-2c963f66afa6&graphNumber=8" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY"
```

### Пример 12: Заполнение документа через importJson

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows/{docflowId}/form/{formId}/importJson" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "ESADout_CUGoodsShipment": {
      "ESADout_CUConsignee": {
        "EqualIndicator": "true"
      },
      "ESADout_CUFinancialAdjustingResponsiblePerson": {
        "DeclarantEqualFlag": "true"
      }
    }
  }'
```

### Пример 13: Печать формы в PDF

```bash
curl -X GET "https://api-d.kontur.ru/common/v1/docflows/{docflowId}/form/{formId}/printPDF" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  --output declaration.pdf
```

### Пример 14: Копирование документооборота

```bash
curl -X POST "https://api-d.kontur.ru/common/v1/docflows/copy" \
  -H "X-Kontur-ApiKey: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "copyFromId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "customs": [],
    "organizationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "employeeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Выпуск для внутреннего потребления ИМ 40"
  }'
```

---

### Пример 15: Получение списка организаций

```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/options/organizations' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

### Пример 16: Получение списка сотрудников организации

```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/options/employees?orgId=12345678-90ab-cdef-1234-567890abcdef' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

### Пример 17: Получение списка таможенных процедур

```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/options/declarationProcedureTypes?declarationType=0' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

### Пример 18: Расчет таможенного платежа при ввозе автомобиля

```bash
curl -X POST 'https://api-d.kontur.ru/common/v1/vehiclePayments/calculate' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "ownerType": 0,
    "age": 3,
    "price": 25000,
    "currencyCode": 840,
    "engineType": 1,
    "fuelType": 1,
    "power": 150,
    "powerUnitMeasurement": 0,
    "engineVolume": 2000
  }'
```

---

### Пример 19: Получение шаблона документа

```bash
curl -X GET 'https://api-d.kontur.ru/common/v1/jsonTemplates/10BS110E' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

### Пример 20: Присоединение документа к товарам

```bash
curl -X POST 'https://api-d.kontur.ru/common/v1/docflows/12345678-90ab-cdef-1234-567890abcdef/documents/document-id/good/1,2' \
  -H 'X-Kontur-ApiKey: YOUR_API_KEY'
```

---

## Коды ошибок

**200 OK** - Успешный запрос

**201 Created** - Ресурс успешно создан (документооборот, документ)

**400 Bad Request** - Некорректные параметры запроса

**401 Unauthorized** - Отсутствует или неверный API ключ / SessionID

**403 Forbidden** - Доступ запрещен

**404 Not Found** - Ресурс не найден / В ДО отсутствуют отметки по ДТ

**500 Internal Server Error** - Внутренняя ошибка сервера

---

---

## 4. Common API - Общие методы

### 4.1 Аутентификация

**Endpoint:** `POST /auth/v1/authenticate`

**Базовый URL:** `https://api-d.kontur.ru`

**Полный URL:** `https://api-d.kontur.ru/auth/v1/authenticate?login={login}&pass={pass}`

**Описание:** Метод аутентификации для получения SessionID (sid)

**Query Parameters:**
- `login` (string, required) - Логин пользователя (email)
  - Пример: `etoai@comfythings.com`
- `pass` (string, required) - Пароль пользователя
  - Пример: `etoaicomfythingscom`

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ для доступа к системе
  - Пример: `84f53197-e8c0-70b8-f608-e45080b06eeb`

**Responses:**
- `200 OK` - Возвращает SessionID (sid) в виде строки
  - Content-Type: `text/plain; charset=utf-8`
  - Response body: `string` (64-символьный hex-код)
  - Пример sid: `407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA`
- `403 Forbidden` - Доступ запрещен (неверные учетные данные или API ключ)

**Важно:** 
- **SessionID (sid)** используется для авторизации во всех остальных методах API
- Полученный **sid** необходимо передавать в заголовке `Authorization` для последующих запросов
- В URL параметры `login` и `pass` передаются как query parameters
- Email в параметре `login` необходимо URL-кодировать (@ → %40)

**Пример запроса:**
```bash
curl -X POST 'https://api-d.kontur.ru/auth/v1/authenticate?login=etoai%40comfythings.com&pass=etoaicomfythingscom' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb'
```

**Response Example:**
```
407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA
```

**Использование SessionID в других методах:**
```bash
# Пример использования полученного sid в других запросах
curl -X GET 'https://api-d.kontur.ru/common/v1/docflows' \
  -H 'X-Kontur-ApiKey: 84f53197-e8c0-70b8-f608-e45080b06eeb' \
  -H 'Authorization: 407EF745D71FBB4F9B4A1B5F7211E7183FA189A88274CF46BA50EF65F8A20BCA'
```

**Примечание:** При успехе возвращается код 200 и `SessionId` (кратко `sid`). Для авторизации в остальных методах нужно заполнить параметр `sid`.

---

### 4.2 Работа с документооборотом

#### 4.2.1 Список документооборотов

**Endpoint:** `GET /common/v1/docflows`

**Описание:** Метод возвращает данные о декларациях, которые отображаются в списке деклараций

**Query Parameters:**
- `take` (integer($int32), query) - Количество записей (Default: 1000)
- `changedFrom` (integer($int64), query) - Фильтр по дате изменения ДО, дата "от"
- `changedTo` (integer($int64), query) - Фильтр по дате изменения ДО, дата "до"
- `status` (integer($int32), query) - Идентификатор статуса документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Массив документооборотов

**Response Example:**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "string",
    "declarationType": 0,
    "procedure": 0,
    "status": 0,
    "changed": "2025-11-30T16:20:56.473Z",
    "created": "2025-11-30T16:20:56.473Z",
    "ownName": "string",
    "inn": "string",
    "kpp": "string",
    "processId": "string",
    "gtdNumber": "string",
    "statusText": "string"
  }
]
```

---

#### 4.2.2 Создание документооборота

**Endpoint:** `POST /common/v1/docflows`

**Описание:** Создание документооборота (декларации, ПИ, ОЭЗ и т.д.)

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body:**
```json
{
  "type": 0,
  "procedure": 0,
  "singularity": 0,
  "customsId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "employeeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string"
}
```

**Responses:**
- `201` - Документооборот создан

**Response Example:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string",
  "declarationType": 0,
  "procedure": 0,
  "status": 0,
  "changed": "2025-11-30T16:21:05.073Z",
  "created": "2025-11-30T16:21:05.073Z",
  "ownName": "string",
  "inn": "string",
  "kpp": "string",
  "processId": "string",
  "gtdNumber": "string",
  "statusText": "string"
}
```

---

#### 4.2.3 Копирование документооборота

**Endpoint:** `POST /common/v1/docflows/copy`

**Описание:** Копирование документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body:**
```json
{
  "copyFromId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "customs": [],
  "organizationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "employeeId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "string"
}
```

**Responses:**
- `201` - Документооборот создан
- `400` - Ошибка
- `401` - Unauthorized
- `403` - Доступ запрещен

---

#### 4.2.4 Поиск документооборота

**Endpoint:** `POST /common/v1/docflows/search`

**Описание:** Поиск документооборота по различным параметрам

**Query Parameters:**
- `take` (integer($int32), query) - Default: 50
- `skip` (integer($int32), query) - Default: 0

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body:**
```json
{
  "query": "string",
  "searchInput": "string",
  "searchedFrom": "2025-11-30T16:22:27.177Z",
  "gtdRegistrationDateTo": "2025-11-30T16:22:27.177Z",
  "createdFrom": "2025-11-30T16:22:27.177Z",
  "createdTo": "2025-11-30T16:22:27.177Z",
  "consignee": "string",
  "sender": "string",
  "documentDateFrom": "2025-11-30T16:22:27.177Z",
  "documentDateTo": "2025-11-30T16:22:27.177Z",
  "presentedDocumentDate": "2025-11-30T16:22:27.177Z",
  "presentedDocumentName": "string",
  "procedure": 0,
  "type": 0,
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "orgIds": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
  "includeDeleted": true,
  "includeDone": true,
  "docflowTags": []
}
```

**Responses:**
- `200 OK` - Список найденных документооборотов

---

#### 4.2.5 Отметки на ДТ

**Endpoint:** `GET /common/v1/docflows/{docflowId}/declarationMarks`

**Описание:** Получение отметок на декларации

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Успешный ответ
- `401 Unauthorized`
- `403 Forbidden`
- `404` - В ДО отсутствуют отметки по ДТ

---

#### 4.2.6 Журнал сообщений

**Endpoint:** `GET /common/v1/docflows/{docflowId}/messages`

**Описание:** Получение журнала сообщений документооборота

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Список сообщений

**Response Example:**
```json
[
  {
    "envelopeId": "string",
    "processingDateTime": "2025-11-30T16:21:28.122Z",
    "preparationDateTime": "2025-11-30T16:21:28.122Z",
    "messageType": "string",
    "messageDescription": "string",
    "envelope": "string"
  }
]
```

---

#### 4.2.7 Установка флага "Документ открыт"

**Endpoint:** `POST /common/v1/docflows/{docflowId}/setOpenedTrue`

**Описание:** Установить данные о том, что главный документ документооборота был открыт

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

---

### 4.3 Работа с документами

#### 4.3.1 Создание документа

**Endpoint:** `POST /common/v1/docflows/{docflowId}/documents`

**Описание:** Создание документа в документообороте

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body Parameters:**
- `name` - Название документа
- `number` - Номер документа
- `date` - Дата документа (ГГГ-ММ-ДД)
- `documentModeId` - Идентификатор формы по альбому форматов ФТС
- `grafa44Code` - Код вида документа
- `providingIndex` - Признак представления
- `isCommon` - Отображать документ в блоке "Регистрационные документы"
- `belongsToAllGoods` - Добавлять документ к каждому товару декларации
- `copyDataFromDt` - При создании, скопировать данные из ДТ
- `copyIfExists` - Если документ с таким номером или датой уже существует – скопировать из него данные

**Responses:**
- `200 OK` - Возвращает `DocumentRowDto`

---

#### 4.3.2 Список документов

**Endpoint:** `GET /common/v1/docflows/{docflowId}/documents`

**Описание:** Получение списка документов документооборота

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Массив `DocumentRowDto`

---

#### 4.3.3 Создание документа с использованием калькулятора расходов

**Endpoint:** `POST /common/v1/docflows/{docflowId}/documents/createDteWithCalculator`

**Описание:** Создание ДТС с калькулятором расходов

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота

**Query Parameters:**
- `dtsType` - Номер ДТС от 1 до 4
- `DistributionItemDto[]` - Распределение расходов по товарам

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body Example:**
```json
[
  {
    "grafa": "17",
    "distributeBy": 1,
    "includeIn": 2,
    "borderPlace": "пограничный пункт",
    "currencyCode": "USD",
    "total": 500
  },
  {
    "grafa": "13A",
    "distributeBy": 2,
    "includeIn": 2,
    "borderPlace": "",
    "currencyCode": "USD",
    "total": 500
  },
  {
    "grafa": "11B",
    "distributeBy": 2,
    "includeIn": 2,
    "borderPlace": "",
    "currencyCode": "USD",
    "total": 100
  }
]
```

**Структура DistributionItemDto:**
- `grafa` - Вид расхода (номер графы в ДТС)
- `distributeBy` - Распределение: 1 - по весу брутто; 2 - по цене; 3 - поровну
- `includeIn` - Включить в: 1 - цену; 2 - таможенную стоимость; 3 - статистическую стоимость
- `currencyCode` - Валюта (трехбуквенный код)
- `total` - Сумма в валюте
- `borderPlace` - Место прибытия

---

#### 4.3.4 Загрузка из файла

**Endpoint:** `POST /common/v1/docflows/{docflowId}/form/{formId}/upload`

**Описание:** Загрузка документа из файла

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Поддерживаемые форматы:**
- Документы с `documentModeId = 10BS110E` - FreeDoc
- Паспорт (расширение `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tiff`)
- XML файлы (автоматическое преобразование в FreeDoc)

**Responses:**
- `200 OK`

---

#### 4.3.5 Заполнение документов через JSON (importJson)

**Endpoint:** `POST /common/v1/docflows/{docflowId}/form/{formId}/importJson`

**Описание:** Универсальный метод заполнения документов через JSON

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body Examples:**

Для графы 8:
```json
{
  "ESADout_CUGoodsShipment": {
    "ESADout_CUConsignee": {
      "EqualIndicator": "true"
    }
  }
}
```

Для графы 9:
```json
{
  "ESADout_CUGoodsShipment": {
    "ESADout_CUFinancialAdjustingResponsiblePerson": {
      "DeclarantEqualFlag": "true"
    }
  }
}
```

Для обеих граф:
```json
{
  "ESADout_CUGoodsShipment": {
    "ESADout_CUConsignee": {
      "EqualIndicator": "true"
    },
    "ESADout_CUFinancialAdjustingResponsiblePerson": {
      "DeclarantEqualFlag": "true"
    }
  }
}
```

**Responses:**
- `200 OK`

---

#### 4.3.6 Загрузка товарной части (import)

**Endpoint:** `POST /common/v1/docflows/{docflowId}/form/{formId}/import`

**Описание:** Импорт данных в форму документа (заполнитель). Для полученных документов с фактурной частью, например, для декларации или инвойса.

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Query Parameters:**
- `clearBeforeUpload` (boolean, query) - Default: false
- `mapOptions` (integer($int32), query) - Available values: 0, 1
- `preserveAttachedGoods` (boolean, query) - Default: true

**Request Body:** `application/json`

**Responses:**
- `200 OK`

---

#### 4.3.7 Получить JSON документа

**Endpoint:** `GET /common/v1/docflows/{docflowId}/form/{formId}/json`

**Описание:** Получить JSON документа

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Возвращает `string` (JSON документа)

---

#### 4.3.8 Скачать XML документа

**Endpoint:** `GET /common/v1/docflows/{docflowId}/form/{formId}/xml`

**Описание:** Скачать XML документа

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Возвращает XML файл

---

#### 4.3.9 Присоединить документ к товарам

**Endpoint:** `POST /common/v1/docflows/{docflowId}/documents/{documentId}/good/{goodNumbers}`

**Описание:** Присоединить документ к товарам интерфейса документооборота

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `documentId` (string($uuid), required) - ID документа
- `goodNumbers` (string, path) - Номера товаров

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Нумерация товаров:** Документ будет отвязан от всех товаров и привязан к указанным. Если передать 0, то документ отвяжется от всех товаров.

**Responses:**
- `200 OK`

---

#### 4.3.10 Скопировать данные из декларации

**Endpoint:** `POST /common/v1/docflows/{docflowId}/documents/{documentId}/copyFromDt`

**Описание:** Скопировать данные из декларации

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `documentId` (string($uuid), required) - Идентификатор документа (не формы)

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200` - Данные скопированы
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Доступ запрещен

---

---

### 4.4 Печать документов

#### 4.4.1 Печать формы в HTML

**Endpoint:** `GET /common/v1/docflows/{docflowId}/form/{formId}/printHtml`

**Описание:** Печать формы в HTML формате

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - HTML документ

---

#### 4.4.2 Печать формы в PDF

**Endpoint:** `GET /common/v1/docflows/{docflowId}/form/{formId}/printPDF`

**Описание:** Печать формы в PDF формате

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - PDF документ

---

### 4.5 Работа с контрагентами

#### 4.5.1 Справочник контрагентов

**Описание:** API позволяет создавать контрагентов всех типов, заполнять соответствующие графы документов, указывая номер графы и идентификатор контрагента.

**Структура CommonOrg:**

Данную структуру принимают и возвращают почти все методы данной категории.

**Свойства:**
- `orgName` - Название организации или ИП
- `shortName` - Произвольное название для удобства пользователя
- `type` - Тип организации (0 - Юридическое лицо; 1 - ИП; 2 - Физическое лицо)
- `legalAddress` - Юридический адрес
- `actualAddress` - Фактический адрес (заполняется только для юридических лиц и только если отличается от `legalAddress`)
- `person` - Заполняется только для физических лиц. При заполнении физических лиц `orgName` и `shortName` не заполняются
- `identityCard` - Заполняется для ИП и физических лиц, для юридических лиц не заполняется
- `branchDescription` - Заполняется, если нам надо описать, что расписано с обособленных подразделениях

**Пример российской организации:**
```json
{
  "type": 0,
  "isForeign": false,
  "orgName": "ООО \"РОМАШКА\"",
  "shortName": "РОМАШКА",
  "inn": "7719483568",
  "kpp": "111111111",
  "ogrn": "1187746252821",
  "okato": "12341234213",
  "okpo": "12341234213",
  "oktmo": "12341234213",
  "legalAddress": {
    "city": "г. Москва",
    "settlement": "",
    "countryName": "РОССИЯ",
    "countryCode": "RU",
    "postalCode": "105318",
    "region": "Москва",
    "streetHouse": "ул. Мироновская",
    "house": "дом 9",
    "room": "кв. 50"
  }
}
```

**Пример иностранной организации:**
```json
{
  "type": 0,
  "isForeign": true,
  "orgName": "SHANGHAI SHAREINDUSTRY CO.,LTD.",
  "shortName": "SHANGHAI SHAREINDUSTRY CO.,LTD.",
  "legalAddress": {
    "city": "TINGLIN TOWN",
    "settlement": "",
    "countryName": "КИТАЙ",
    "countryCode": "CN",
    "postalCode": "201505",
    "region": "JINSHAN DISTRICT SHANGHAI",
    "streetHouse": "SONGYIHUCAI ROAD",
    "house": "BUILDING 1, NO.22, LANE 121",
    "room": "ROOM 1914"
  }
}
```

---

#### 4.5.2 Создание/получение организаций

**Endpoint:** `POST /common/v1/commonOrganizations`

**Описание:** Принимает структуру `CommonOrg`. Если такая организация уже есть, то она обновляется. Если нет - создаётся.

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body:** См. структуру `CommonOrg`

**Responses:**
- `200 OK` - Возвращает `CommonOrg` с заполненным `id`

---

#### 4.5.3 Получение контрагента по ИНН

**Endpoint:** `POST /common/v1/getOrCreateCommonOrgByInn`

**Описание:** Получение или создание российской организации по ИНН

**Query Parameters:**
- `inn` (string) - ИНН организации

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Возвращает `CommonOrg` для организации с указанным ИНН

**Примечание:** Контрагент имеет достаточно большое количество полей, и программист не всегда имеет их все под рукой. Для российских организаций можно использовать этот метод.

---

#### 4.5.4 Использование справочника в документах

**Endpoint:** `POST /common/v1/docflows/{docflowId}/form/{formId}/setCommonOrg?commonOrgId={commonOrgId}&graphNumber={graphNumber}`

**Описание:** Установка контрагента в документ

**Path Parameters:**
- `docflowId` (string($uuid), required) - ID документооборота
- `formId` (string($uuid), required) - ID формы

**Query Parameters:**
- `commonOrgId` (string($uuid)) - ID контрагента
- `graphNumber` (integer) - Номер графы

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

---

## Примечания

1. Все даты передаются в формате ISO 8601: `YYYY-MM-DDTHH:mm:ss.sssZ`
2. Для всех запросов обязателен заголовок `X-Kontur-ApiKey`
3. Content-Type для POST запросов: `application/json`
4. Коды ТНВЭД должны передаваться в формате 10 знаков
5. Коды стран передаются в формате ISO 3166-1 alpha-2 (2 символа)
6. SessionId (sid) получается через метод аутентификации и используется для авторизации

---

---

## 6. Options API - Справочники

Справочная информация для работы с API.

### 6.1 Организации

**Endpoint:** `GET /common/v1/options/organizations`

**Описание:** Список доступных организаций

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Массив объектов организаций

**Структура ответа:**
```json
[
  {
    "id": "string",
    "participationIds": "string",
    "name": "string",
    "inn": "string",
    "kpp": "string",
    "ogrn": "string",
    "okpo": "string",
    "okato": "string",
    "oktmo": "string",
    "address": {
      "building": "string",
      "city": "string",
      "district": "string",
      "flat": "string",
      "house": "string",
      "region": "string",
      "street": "string"
    }
  }
]
```

---

### 6.2 Сотрудники

**Endpoint:** `GET /common/v1/options/employees`

**Описание:** Список доступных сотрудников для организации

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Query Parameters:**
- `orgId` (string($uuid), query) - ID организации

**Responses:**
- `200 OK` - Массив объектов сотрудников
- `400` - Не заполнен индентификатор организации
- `403` - Доступ запрещен

**Структура ответа:**
```json
[
  {
    "id": "string",
    "surname": "string",
    "name": "string",
    "patronymic": "string",
    "phone": "string",
    "email": "string",
    "passportOrganization": "string",
    "passportDate": "2025-11-30T16:25-48.812Z",
    "passportNumber": "string",
    "identity": 0,
    "authLetterDate": "string",
    "authLetterNumber": "string"
  }
]
```

---

### 6.3 Типы деклараций

**Endpoint:** `GET /common/v1/options/declarationTypes`

**Описание:** Список направлений перемещения

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

**Структура ответа:**
```json
[
  {
    "id": 0,
    "description": "string"
  }
]
```

---

### 6.4 Таможенные процедуры

**Endpoint:** `GET /common/v1/options/declarationProcedureTypes`

**Описание:** Список таможенных процедур

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Query Parameters:**
- `declarationType` (integer($int32), query) - Тип декларации
  - **Available values:** 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46

**Responses:**
- `200 OK`
- `400` - Не заполнен индентификатор направления перемещения

**Структура ответа:**
```json
[
  {
    "id": 0,
    "code": "string",
    "name": "string"
  }
]
```

---

### 6.5 Особенности декларации

**Endpoint:** `GET /common/v1/options/declarationSingularities`

**Описание:** Список особенностей декларации

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Query Parameters:**
- `declarationType` (integer($int32), query) - Тип декларации
  - **Available values:** 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46

**Responses:**
- `200 OK`

**Структура ответа:**
```json
[
  {
    "id": 0,
    "shortName": "string",
    "name": "string"
  }
]
```

---

### 6.6 Таможенные органы

**Endpoint:** `GET /common/v1/options/customs`

**Описание:** Список таможенных органов

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

**Структура ответа:**
```json
[
  {
    "id": 0,
    "shortName": "string",
    "name": "string"
  }
]
```

---

### 6.7 Справочник контрагентов

**Endpoint:** `GET /common/v1/options/commonOrgs`

**Описание:** Справочник контрагентов

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

**Структура ответа:** См. CommonOrg в разделе "Схемы данных"

---

## 7. JsonTemplates API - Шаблоны

### 7.1 Список шаблонов

**Endpoint:** `GET /common/v1/jsonTemplates`

**Описание:** Получить список доступных шаблонов

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK`

**Структура ответа:**
```json
[
  {
    "id": "string",
    "documentModeId": "string",
    "typeName": "string"
  }
]
```

---

### 7.2 Получить шаблон документа

**Endpoint:** `GET /common/v1/jsonTemplates/{documentModeId}`

**Описание:** Получить шаблон документа по documentModeId

**Path Parameters:**
- `documentModeId` (string, required) - ID режима документа

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Responses:**
- `200 OK` - Возвращает `string` (JSON шаблон документа)

---

## 8. VehiclePayments API - Платежи при ввозе автомобиля

### 8.1 Расчет таможенного платежа

**Endpoint:** `POST /common/v1/vehiclePayments/calculate`

**Описание:** Расчет таможенного платежа при ввозе автомобиля

**Headers:**
- `X-Kontur-ApiKey` (required) - API ключ

**Request Body:** `application/json`

**Структура запроса:**
```json
{
  "ownerType": 0,
  "age": 0,
  "price": 0,
  "currencyCode": 0,
  "engineType": 0,
  "fuelType": 0,
  "hybridElectricBattery": true,
  "power": 0,
  "powerUnitMeasurement": 0,
  "electricalPower": 0,
  "electricalPowerUnitMeasurement": 0,
  "environmentalClass": 0,
  "hasSequentialTypeOfPowerUnit": true,
  "engineVolume": 0
}
```

**Responses:**
- `200 OK`
- `401` - Unauthorized
- `403` - Forbidden

**Структура ответа:**
```json
{
  "isTnved": "string",
  "payments": [
    {
      "name": "string",
      "taxBase": "string",
      "rate": "string",
      "paymentInRubles": 0,
      "payment": 0,
      "currencyCode": 0,
      "currencyCodeAlphabetical": "string"
    }
  ],
  "totalPaymentInRubles": 0,
  "totalPayment": 0,
  "currencyCode": 0,
  "currencyCodeAlphabetical": "string"
}
```

---

## Часто задаваемые вопросы (FAQ)

### 1. Как получить доступ к API?

Для получения доступа к API вам нужен логин, пароль и API-ключ. Если вы хотите попробовать, свяжитесь с Контур.Декларант через форму обратной связи.

### 2. Как создать документооборот?

Используйте метод `POST /common/v1/docflows` с указанием типа документооборота, таможенной процедуры и организации.

### 3. Как заполнить документ?

Есть несколько способов:
- Загрузка из файла (XML, PDF, DOCX): `POST /common/v1/docflows/{docflowId}/form/{formId}/upload`
- Заполнение через JSON: `POST /common/v1/docflows/{docflowId}/form/{formId}/importJson`
- Создание с использованием калькулятора расходов: `POST /common/v1/docflows/{docflowId}/documents/createDteWithCalculator`

### 4. Как работать с контрагентами?

Для российских организаций можно использовать метод `POST /common/v1/getOrCreateCommonOrgByInn?inn={ИНН}`, который автоматически получит данные по ИНН.

Для иностранных организаций используйте `POST /common/v1/commonOrganizations` с полной структурой `CommonOrg`.

### 5. Как рассчитать таможенные платежи?

Используйте метод `POST /references/v1/tnved/calculate` с указанием кода ТНВЭД, даты, страны, цены и количества товара.

### 6. Как получить ставки по коду ТНВЭД?

Метод `GET /references/v1/tnved/rates?tnvedCode={код}&dateTime={дата}` возвращает все импортные и экспортные ставки для указанного кода.

### 7. Как распечатать документ?

- HTML формат: `GET /common/v1/docflows/{docflowId}/form/{formId}/printHtml`
- PDF формат: `GET /common/v1/docflows/{docflowId}/form/{formId}/printPDF`

### 8. Как скопировать документооборот?

Используйте метод `POST /common/v1/docflows/copy` с указанием ID исходного документооборота (`copyFromId`).

### 9. Какие форматы файлов поддерживаются для загрузки?

- XML (таможенный формат)
- PDF, JPG, JPEG, PNG, TIFF (для паспортов и сканов)
- DOCX (FreeDoc)

### 10. Как искать документооборот?

Метод `POST /common/v1/docflows/search` позволяет искать по различным параметрам: дате создания, типу, процедуре, отправителю, получателю и т.д.

---

## Контакты

**Техническая поддержка:** Contact Контур.Декларант

**Swagger JSON:**
- PAO API: https://api-d.kontur.ru/docs/pao.v1/swagger.json
- NAG API: https://api-d.kontur.ru/docs/nag.v1/swagger.json
- References API: https://api-d.kontur.ru/docs/references.v1/swagger.json
- Common API: https://api-d.kontur.ru/docs/common.v1/swagger.json
