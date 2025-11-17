
-- 1) Предотвращение эскалации привилегий через profiles.developer
create or replace function public.prevent_developer_escalation()
returns trigger
language plpgsql
security definer
set search_path = 'public'
as $$
begin
  if TG_OP = 'UPDATE' then
    -- Разрешаем менять developer только действующим разработчикам
    if coalesce(NEW.developer, false) is distinct from coalesce(OLD.developer, false) then
      if public.is_current_user_developer() is not true then
        raise exception 'INSUFFICIENT_PRIVILEGES: only developers can change developer flag';
      end if;
    end if;
  end if;
  return NEW;
end;
$$;

drop trigger if exists trg_prevent_developer_escalation on public.profiles;

create trigger trg_prevent_developer_escalation
before update on public.profiles
for each row
execute procedure public.prevent_developer_escalation();

-- 2) Жестче RLS для public.tg_users (только разработчики)
alter table public.tg_users enable row level security;

-- Удаляем небезопасную и дублирующие политики
drop policy if exists "Authenticated users can view own data" on public.tg_users;
drop policy if exists "Developers full access to tg_users" on public.tg_users;
drop policy if exists "Developers can manage tg_users" on public.tg_users;

-- Создаем единую политику: разработчики могут всё
create policy "Developers can manage tg_users"
on public.tg_users
for all
to authenticated
using (public.is_user_developer())
with check (public.is_user_developer());

-- Примечание: существующую политику
-- "Service role can insert verified users" (INSERT) оставляем без изменений
