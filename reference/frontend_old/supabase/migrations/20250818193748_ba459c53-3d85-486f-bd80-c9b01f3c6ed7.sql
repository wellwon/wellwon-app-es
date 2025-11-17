-- 1) Вспомогательные функции доступа

create or replace function public.is_active_employee()
returns boolean
language sql
stable
security definer
set search_path = 'public'
as $$
  select exists (
    select 1
    from public.profiles
    where user_id = auth.uid()
      and active = true
  );
$$;

create or replace function public.can_access_chat(chat_uuid uuid)
returns boolean
language sql
stable
security definer
set search_path = 'public'
as $$
  select
    -- Разработчики всегда имеют доступ
    coalesce((select developer from public.profiles where user_id = auth.uid()), false)
    or
    -- Участник чата
    exists (
      select 1
      from public.chat_participants cp
      where cp.chat_id = chat_uuid
        and cp.user_id = auth.uid()
        and cp.is_active = true
    )
    or
    -- Любой активный сотрудник видит все активные чаты активных Telegram супергрупп
    (
      public.is_active_employee()
      and exists (
        select 1
        from public.chats c
        join public.telegram_supergroups t on t.id = c.telegram_supergroup_id
        where c.id = chat_uuid
          and c.is_active = true
          and t.is_active = true
      )
    );
$$;

-- 2) RLS на messages: разрешить просмотр/отправку всем, кто проходит public.can_access_chat

drop policy if exists "Users can view messages in their chats" on public.messages;
create policy "Employees can view messages by can_access_chat"
  on public.messages
  for select
  using (public.can_access_chat(chat_id));

drop policy if exists "Users can send messages to their chats" on public.messages;
create policy "Employees can insert messages by can_access_chat"
  on public.messages
  for insert
  with check ((auth.uid() = sender_id) and public.can_access_chat(chat_id));

-- 3) RLS на chats: заменить на доступ через public.can_access_chat

drop policy if exists "Simple chats view" on public.chats;
create policy "Employees can view chats by can_access_chat"
  on public.chats
  for select
  using (public.can_access_chat(id));

-- Политику INSERT оставляем как есть:
-- "Users can create chats" WITH CHECK (auth.uid() = created_by)

-- 4) Разрешить всем активным сотрудникам читать активные Telegram супергруппы

drop policy if exists "Users can view active supergroups" on public.telegram_supergroups;
create policy "Users can view active supergroups"
  on public.telegram_supergroups
  for select
  using (is_active = true and public.is_active_employee());

-- 5) Ослабить RPC для получения чатов по супергруппе (чтобы не требовало участия/флага developer)

create or replace function public.get_user_chats_by_supergroup(user_uuid uuid, supergroup_id_param bigint)
returns table(
  id uuid,
  name text,
  type text,
  created_by uuid,
  created_at timestamptz,
  updated_at timestamptz,
  is_active boolean,
  metadata jsonb,
  company_id bigint,
  chat_number integer,
  telegram_supergroup_id bigint,
  telegram_topic_id integer,
  telegram_sync boolean
)
language sql
stable
security definer
set search_path = 'public'
as $function$
  select 
    c.id, 
    c.name, 
    c.type, 
    c.created_by, 
    c.created_at, 
    c.updated_at, 
    c.is_active, 
    c.metadata, 
    c.company_id, 
    c.chat_number,
    c.telegram_supergroup_id,
    c.telegram_topic_id,
    c.telegram_sync
  from public.chats c
  join public.telegram_supergroups t on t.id = c.telegram_supergroup_id
  where c.is_active = true
    and t.is_active = true
    and c.telegram_supergroup_id = supergroup_id_param
  order by c.updated_at desc;
$function$;

-- 6) Обновить функцию доступа, которую может использовать edge-функция (если она обращается к RPC):
-- Разрешим доступ, если can_access_chat = true

create or replace function public.get_chat_with_telegram_data(chat_uuid uuid)
returns table(
  id uuid,
  name text,
  type text,
  company_id bigint,
  telegram_sync boolean,
  telegram_supergroup_id bigint,
  telegram_topic_id integer,
  created_at timestamptz,
  updated_at timestamptz
)
language sql
stable
security definer
set search_path = 'public'
as $function$
  select 
    c.id,
    c.name,
    c.type,
    c.company_id,
    c.telegram_sync,
    c.telegram_supergroup_id,
    c.telegram_topic_id,
    c.created_at,
    c.updated_at
  from public.chats c
  where c.id = chat_uuid
    and public.can_access_chat(c.id);
$function$;

-- 7) Добавить ответственного за супергруппу

alter table public.telegram_supergroups
  add column if not exists responsible_user_id uuid;

create or replace function public.set_default_supergroup_responsible()
returns trigger
language plpgsql
security definer
set search_path = 'public'
as $$
begin
  if tg_op = 'INSERT' then
    if new.responsible_user_id is null then
      new.responsible_user_id := auth.uid();
    end if;
  elsif tg_op = 'UPDATE' then
    if new.responsible_user_id is null and old.responsible_user_id is null then
      new.responsible_user_id := auth.uid();
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists set_default_supergroup_responsible_ins on public.telegram_supergroups;
create trigger set_default_supergroup_responsible_ins
  before insert on public.telegram_supergroups
  for each row
  execute function public.set_default_supergroup_responsible();

drop trigger if exists set_default_supergroup_responsible_upd on public.telegram_supergroups;
create trigger set_default_supergroup_responsible_upd
  before update on public.telegram_supergroups
  for each row
  execute function public.set_default_supergroup_responsible();

-- (Опционально) Если хотите, чтобы «набор печатает…» и «прочитано» тоже работали без участия в чате:
-- message_reads: разрешить вставку по can_access_chat
drop policy if exists "Users can mark messages as read" on public.message_reads;
create policy "Employees can mark read if can_access_chat"
  on public.message_reads
  for insert
  with check (
    user_id = auth.uid()
    and public.can_access_chat( (select m.chat_id from public.messages m where m.id = message_reads.message_id) )
  );

-- typing_indicators: разрешить set/update/select по can_access_chat
drop policy if exists "Users can set typing indicators in their chats" on public.typing_indicators;
create policy "Employees can set typing indicators if can_access_chat"
  on public.typing_indicators
  for insert
  with check (
    auth.uid() = user_id
    and public.can_access_chat(chat_id)
  );

drop policy if exists "Users can update their typing indicators" on public.typing_indicators;
create policy "Employees can update their typing indicators"
  on public.typing_indicators
  for update
  using (auth.uid() = user_id);

drop policy if exists "Users can view typing indicators in their chats" on public.typing_indicators;
create policy "Employees can view typing indicators if can_access_chat"
  on public.typing_indicators
  for select
  using (public.can_access_chat(chat_id));