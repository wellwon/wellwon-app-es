
-- 1) Функция для UPSERT в tg_users на основе telegram_group_members
create or replace function public.upsert_tg_user_from_member()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
begin
  insert into public.tg_users as u (id, first_name, last_name, username, is_bot)
  values (
    new.telegram_user_id,
    coalesce(nullif(new.first_name, ''), nullif(new.username, ''), 'Unknown'),
    nullif(new.last_name, ''),
    nullif(new.username, ''),
    coalesce(new.is_bot, false)
  )
  on conflict (id) do update
  set
    first_name = coalesce(excluded.first_name, u.first_name),
    last_name  = coalesce(excluded.last_name,  u.last_name),
    username   = coalesce(excluded.username,   u.username),
    is_bot     = coalesce(excluded.is_bot,     u.is_bot),
    updated_at = timezone('utc', now());
  return new;
end;
$$;

-- 2) Триггеры: на вставку и на обновление ключевых полей
drop trigger if exists trg_tg_users_sync_from_members_ins on public.telegram_group_members;
create trigger trg_tg_users_sync_from_members_ins
after insert on public.telegram_group_members
for each row
execute function public.upsert_tg_user_from_member();

drop trigger if exists trg_tg_users_sync_from_members_upd on public.telegram_group_members;
create trigger trg_tg_users_sync_from_members_upd
after update of first_name, last_name, username, is_bot on public.telegram_group_members
for each row
when (new.telegram_user_id is not null)
execute function public.upsert_tg_user_from_member();

-- 3) Бэкофилл: внести недостающих пользователей в tg_users из существующих участников групп
insert into public.tg_users (id, first_name, last_name, username, is_bot)
select distinct
  tgm.telegram_user_id,
  coalesce(nullif(tgm.first_name, ''), nullif(tgm.username, ''), 'Unknown'),
  nullif(tgm.last_name, ''),
  nullif(tgm.username, ''),
  coalesce(tgm.is_bot, false)
from public.telegram_group_members tgm
left join public.tg_users tu on tu.id = tgm.telegram_user_id
where tu.id is null;

-- 4) Дозаполнить пропуски, если в tg_users есть null, а в участниках есть значения
with latest as (
  select distinct on (telegram_user_id)
         telegram_user_id, first_name, last_name, username, is_bot
  from public.telegram_group_members
  order by telegram_user_id, joined_at desc
)
update public.tg_users tu
set
  first_name = coalesce(tu.first_name, coalesce(nullif(latest.first_name,''), nullif(latest.username,''), 'Unknown')),
  last_name  = coalesce(tu.last_name,  nullif(latest.last_name,'')),
  username   = coalesce(tu.username,   nullif(latest.username,'')),
  is_bot     = coalesce(tu.is_bot,     latest.is_bot),
  updated_at = timezone('utc', now())
from latest
where tu.id = latest.telegram_user_id
  and (tu.first_name is null or tu.last_name is null or tu.username is null or tu.is_bot is null);
