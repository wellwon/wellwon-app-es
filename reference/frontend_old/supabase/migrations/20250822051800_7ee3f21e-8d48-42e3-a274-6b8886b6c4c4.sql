
-- 1) Добавляем текстовые поля роли для свободного ввода
alter table public.tg_users
  add column if not exists role_label text;

alter table public.profiles
  add column if not exists role_label text;

-- Примечание:
-- NULL в этих колонках означает "Нет роли". Ограничений/дефолтов не добавляем.
