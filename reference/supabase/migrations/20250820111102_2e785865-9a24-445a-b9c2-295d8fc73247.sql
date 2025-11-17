
-- 1) Создаем бакет company-logos (если уже существует — ничего не делаем)
insert into storage.buckets (id, name, public)
values ('company-logos', 'company-logos', true)
on conflict (id) do nothing;

-- 2) Политика: публичное чтение метаданных объектов из company-logos
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'Public read access for company-logos'
  ) then
    create policy "Public read access for company-logos"
      on storage.objects for select
      using (bucket_id = 'company-logos');
  end if;
end$$;

-- 3) Политика: аутентифицированные могут загружать в company-logos
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'Authenticated can upload to company-logos'
  ) then
    create policy "Authenticated can upload to company-logos"
      on storage.objects for insert
      with check (bucket_id = 'company-logos' and auth.role() = 'authenticated');
  end if;
end$$;

-- 4) Политика: владелец может обновлять файлы в company-logos
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'Owner can update company-logos'
  ) then
    create policy "Owner can update company-logos"
      on storage.objects for update
      using (bucket_id = 'company-logos' and owner = auth.uid());
  end if;
end$$;

-- 5) Политика: владелец может удалять файлы в company-logos
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'Owner can delete company-logos'
  ) then
    create policy "Owner can delete company-logos"
      on storage.objects for delete
      using (bucket_id = 'company-logos' and owner = auth.uid());
  end if;
end$$;
