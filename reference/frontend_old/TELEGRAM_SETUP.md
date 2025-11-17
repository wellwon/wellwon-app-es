# Настройка Telegram бота для WellWon

## Обзор секретов

### TELEGRAM_BOT_TOKEN
- **Что это**: Токен бота, полученный от @BotFather
- **Источник**: При создании бота в Telegram получаете токен вида `1234567890:ABCdefGHIjklMNOpqrSTUvwxyz`
- **Назначение**: Используется для API вызовов к Telegram
- **Безопасность**: НЕ публикуйте этот токен! Храните в секретах.

### TELEGRAM_WEBHOOK_SECRET
- **Что это**: Любая случайная строка, которую вы придумываете
- **Назначение**: Telegram отправляет этот секрет в заголовке `X-Telegram-Bot-Api-Secret-Token` для проверки подлинности webhook
- **Важно**: Это РАЗНЫЕ секреты с TELEGRAM_BOT_TOKEN. Они НЕ должны совпадать!
- **Пример**: `mysecretstring123` или любая другая случайная строка

## Ручная настройка webhook

### Установка webhook

```bash
curl -X POST "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://qqhuwvveovmfyihjnanx.supabase.co/functions/v1/telegram-webhook",
    "secret_token": "{TELEGRAM_WEBHOOK_SECRET}",
    "allowed_updates": [
      "message",
      "edited_message", 
      "channel_post",
      "edited_channel_post",
      "callback_query",
      "chat_member",
      "my_chat_member",
      "forum_topic_created",
      "forum_topic_edited",
      "message_reaction",
      "message_reaction_count"
    ],
    "drop_pending_updates": true
  }'
```

### Проверка webhook

```bash
curl "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

**Ожидаемый успешный ответ:**
```json
{
  "ok": true,
  "result": {
    "url": "https://qqhuwvveovmfyihjnanx.supabase.co/functions/v1/telegram-webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "allowed_updates": [
      "message",
      "edited_message",
      "channel_post", 
      "edited_channel_post",
      "callback_query",
      "chat_member",
      "my_chat_member",
      "forum_topic_created",
      "forum_topic_edited",
      "message_reaction",
      "message_reaction_count"
    ]
  }
}
```

## Используемые типы обновлений

Наш бот обрабатывает следующие типы обновлений от Telegram:

- `message` - новые сообщения
- `edited_message` - отредактированные сообщения  
- `channel_post` - посты в каналах
- `edited_channel_post` - отредактированные посты в каналах
- `callback_query` - нажатия на inline кнопки
- `chat_member` - изменения участников чата
- `my_chat_member` - изменения статуса нашего бота в чате
- `forum_topic_created` - создание топиков в форумах
- `forum_topic_edited` - редактирование топиков в форумах  
- `message_reaction` - реакции на сообщения
- `message_reaction_count` - счётчики реакций

## Проверка и отладка

### Проверить статус бота
```bash
curl "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
```

### Логи входящего webhook
Логи обработки входящих сообщений от Telegram:
[Supabase Dashboard - telegram-webhook logs](https://supabase.com/dashboard/project/qqhuwvveovmfyihjnanx/functions/telegram-webhook/logs)

### Тестирование
1. После настройки webhook откройте чат с ботом @wellwon_bot
2. Отправьте команду `/start`
3. Бот должен ответить приветственным сообщением
4. Проверьте логи webhook для отслеживания работы

### Возможные проблемы
- **Ошибка 401**: Неверный TELEGRAM_BOT_TOKEN
- **Ошибка 400**: Неверный формат webhook URL или параметров
- **Timeout**: Проблемы с доступностью edge функции
- **Webhook не срабатывает**: Проверьте логи edge функции и корректность секретов