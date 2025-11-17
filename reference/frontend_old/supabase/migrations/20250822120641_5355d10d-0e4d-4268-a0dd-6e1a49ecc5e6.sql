
-- 1) Сделать bucket chat-files публичным (если уже существует)
update storage.buckets
set public = true
where id = 'chat-files';

-- 2) Политика на чтение списка объектов (list/select) для chat-files
-- (не влияет на публичные прямые ссылки, но полезно для list операций)
drop policy if exists "Public can list chat-files" on storage.objects;
create policy "Public can list chat-files"
on storage.objects
for select
using (bucket_id = 'chat-files');

-- 3) Добавляем служебные поля под медиалогику
alter table public.messages
  add column if not exists telegram_file_id text,
  add column if not exists telegram_file_path text,
  add column if not exists file_status text not null default 'stored';

-- 4) Индекс по telegram_file_id для быстрых бэкфиллов/поиска
create index if not exists idx_messages_telegram_file_id
  on public.messages(telegram_file_id);
