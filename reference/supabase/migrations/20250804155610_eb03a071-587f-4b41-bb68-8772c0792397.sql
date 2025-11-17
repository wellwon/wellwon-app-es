-- Add test users as participants to the existing "Dev" chat
-- First, get the chat ID and user IDs we need
INSERT INTO public.chat_participants (chat_id, user_id, role, joined_at, is_active)
SELECT 
    c.id as chat_id,
    p.user_id,
    'member'::text as role,
    now() as joined_at,
    true as is_active
FROM public.chats c
CROSS JOIN public.profiles p
WHERE c.name = 'Dev' 
  AND p.user_id IN (
    SELECT au.id 
    FROM auth.users au 
    WHERE au.email IN ('oleg.client@test.com', 'oleg.performer@test.com', 'oleg.admin@test.com')
  )
ON CONFLICT (chat_id, user_id) DO NOTHING;

-- Add some test messages from different users to the Dev chat
INSERT INTO public.messages (chat_id, sender_id, content, message_type, created_at)
SELECT 
    c.id as chat_id,
    client_profile.user_id as sender_id,
    'Привет! Я клиент, нужна помощь с заказом' as content,
    'text'::text as message_type,
    now() - interval '2 hours' as created_at
FROM public.chats c
CROSS JOIN public.profiles client_profile
CROSS JOIN auth.users client_user
WHERE c.name = 'Dev'
  AND client_profile.user_id = client_user.id
  AND client_user.email = 'oleg.client@test.com'
LIMIT 1;

INSERT INTO public.messages (chat_id, sender_id, content, message_type, created_at)
SELECT 
    c.id as chat_id,
    performer_profile.user_id as sender_id,
    'Добро пожаловать! Я исполнитель, готов помочь с вашим заказом' as content,
    'text'::text as message_type,
    now() - interval '1 hour' as created_at
FROM public.chats c
CROSS JOIN public.profiles performer_profile
CROSS JOIN auth.users performer_user
WHERE c.name = 'Dev'
  AND performer_profile.user_id = performer_user.id
  AND performer_user.email = 'oleg.performer@test.com'
LIMIT 1;

INSERT INTO public.messages (chat_id, sender_id, content, message_type, created_at)
SELECT 
    c.id as chat_id,
    admin_profile.user_id as sender_id,
    'Админ присоединился к чату для модерации' as content,
    'text'::text as message_type,
    now() - interval '30 minutes' as created_at
FROM public.chats c
CROSS JOIN public.profiles admin_profile
CROSS JOIN auth.users admin_user
WHERE c.name = 'Dev'
  AND admin_profile.user_id = admin_user.id
  AND admin_user.email = 'oleg.admin@test.com'
LIMIT 1;

INSERT INTO public.messages (chat_id, sender_id, content, message_type, created_at)
SELECT 
    c.id as chat_id,
    client_profile.user_id as sender_id,
    'Отлично, спасибо за быстрый ответ!' as content,
    'text'::text as message_type,
    now() - interval '15 minutes' as created_at
FROM public.chats c
CROSS JOIN public.profiles client_profile
CROSS JOIN auth.users client_user
WHERE c.name = 'Dev'
  AND client_profile.user_id = client_user.id
  AND client_user.email = 'oleg.client@test.com'
LIMIT 1;