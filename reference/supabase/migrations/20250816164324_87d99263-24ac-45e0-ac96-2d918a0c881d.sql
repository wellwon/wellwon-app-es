
-- 1) Создать публичный бакет 'company-logos', если его нет
insert into storage.buckets (id, name, public)
select 'company-logos', 'company-logos', true
where not exists (
  select 1 from storage.buckets where id = 'company-logos'
);

-- 2) Политики доступа для storage.objects (company-logos)
do $$
begin
  if not exists (
    select 1 from pg_policies 
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'Public read company-logos'
  ) then
    create policy "Public read company-logos"
      on storage.objects
      for select
      using (bucket_id = 'company-logos');
  end if;
end$$;

do $$
begin
  if not exists (
    select 1 from pg_policies 
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'Authenticated upload company-logos'
  ) then
    create policy "Authenticated upload company-logos"
      on storage.objects
      for insert
      to authenticated
      with check (bucket_id = 'company-logos');
  end if;
end$$;

do $$
begin
  if not exists (
    select 1 from pg_policies 
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'Authenticated update company-logos'
  ) then
    create policy "Authenticated update company-logos"
      on storage.objects
      for update
      to authenticated
      using (bucket_id = 'company-logos')
      with check (bucket_id = 'company-logos');
  end if;
end$$;

do $$
begin
  if not exists (
    select 1 from pg_policies 
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'Authenticated delete company-logos'
  ) then
    create policy "Authenticated delete company-logos"
      on storage.objects
      for delete
      to authenticated
      using (bucket_id = 'company-logos');
  end if;
end$$;
