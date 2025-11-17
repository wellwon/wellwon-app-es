-- Изменить тип company_id в таблице chats с uuid на bigint для соответствия таблице companies
ALTER TABLE public.chats 
ALTER COLUMN company_id TYPE bigint USING NULL;

-- Теперь привязать активный чат к компании  
UPDATE public.chats 
SET company_id = 53 
WHERE id = '19075232-9de9-402a-9043-129786699fa1';