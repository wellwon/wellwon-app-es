
-- 1) Индекс для ускорения
create index if not exists idx_messages_reply_to_id on public.messages(reply_to_id);

-- 2) Внешний ключ (если ещё нет)
do $$
begin
  if not exists (
    select 1 from pg_constraint 
    where conname = 'messages_reply_to_id_fkey'
  ) then
    alter table public.messages
      add constraint messages_reply_to_id_fkey
      foreign key (reply_to_id) references public.messages(id)
      on delete set null;
  end if;
end$$;

-- 3) Валидационный триггер: reply_to_id должен указывать на сообщение в этом же чате,
-- иначе сбрасываем в NULL (мягкая политика, чтобы не ломать отправку)
create or replace function public.validate_message_reply_to()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
begin
  if new.reply_to_id is not null then
    if not exists (
      select 1 from public.messages m
      where m.id = new.reply_to_id
        and m.chat_id = new.chat_id
    ) then
      new.reply_to_id := null;
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_validate_message_reply_to on public.messages;
create trigger trg_validate_message_reply_to
before insert or update on public.messages
for each row execute function public.validate_message_reply_to();

-- 4) Разовая чистка для текущего чата:
-- Сбрасываем реплаи на "пустое" сообщение (message_type = 'other' и без контента/файла)
update public.messages
set reply_to_id = null
where chat_id = '4cb73986-5887-4fc1-b855-bf330acae6a9'
  and reply_to_id in (
    select id
    from public.messages
    where chat_id = '4cb73986-5887-4fc1-b855-bf330acae6a9'
      and coalesce(content, '') = ''
      and file_url is null
      and (message_type is null or message_type = 'other')
  );
