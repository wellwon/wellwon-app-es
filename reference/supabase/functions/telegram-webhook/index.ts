import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders } from "../_shared/cors.ts";

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const telegramWebhookSecret = Deno.env.get('TELEGRAM_WEBHOOK_SECRET');

// Function to get bot token with fallback
function getBotToken(): string | null {
  return Deno.env.get('TELEGRAM_BOT_TOKEN') || Deno.env.get('TELEGRAM_BOT_TOKEN_SEND') || null;
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

interface TelegramMessage {
  message_id: number;
  from: {
    id: number;
    is_bot: boolean;
    first_name: string;
    last_name?: string;
    username?: string;
    language_code?: string;
  };
  chat: {
    id: number;
    type: string;
    title?: string;
    username?: string;
    description?: string;
    invite_link?: string;
    pinned_message?: any;
    permissions?: any;
    slow_mode_delay?: number;
    message_auto_delete_time?: number;
    has_protected_content?: boolean;
    sticker_set_name?: string;
    can_set_sticker_set?: boolean;
    linked_chat_id?: number;
    location?: any;
    is_forum?: boolean; // Добавляем поддержку is_forum
  };
  date: number;
  text?: string;
  entities?: any[];
  caption?: string;
  photo?: any[];
  video?: any;
  document?: any;
  audio?: any;
  voice?: any;
  sticker?: any;
  reply_to_message?: TelegramMessage;
  forward_from?: any;
  forward_from_chat?: any;
  forward_from_message_id?: number;
  forward_signature?: string;
  forward_sender_name?: string;
  forward_date?: number;
  message_thread_id?: number;
  is_topic_message?: boolean; // Добавляем поддержку is_topic_message
  forum_topic_created?: {
    name: string;
    icon_color?: number;
    icon_custom_emoji_id?: string;
  };
  forum_topic_edited?: {
    name?: string;
    icon_custom_emoji_id?: string;
  };
}

interface TelegramUpdate {
  update_id: number;
  message?: TelegramMessage;
  edited_message?: TelegramMessage;
  channel_post?: TelegramMessage;
  edited_channel_post?: TelegramMessage;
  inline_query?: any;
  chosen_inline_result?: any;
  callback_query?: any;
  shipping_query?: any;
  pre_checkout_query?: any;
  poll?: any;
  poll_answer?: any;
  my_chat_member?: any;
  chat_member?: any;
  chat_join_request?: any;
}

// Function to normalize telegram supergroup ID
function normalizeTelegramSupergroupId(id: number): number {
  // If positive ID, add -100 prefix by making it negative and subtracting 1000000000000
  if (id > 0) {
    return id * -1 - 1000000000000;
  }
  // If already negative, return as is
  return id;
}

// Функция для получения или создания супергруппы в базе данных
async function ensureSupergroupExists(chat: TelegramMessage['chat']) {
  if (chat.type !== 'supergroup' && chat.type !== 'group') {
    return null;
  }

  // Normalize the supergroup ID
  const normalizedId = normalizeTelegramSupergroupId(chat.id);
  console.log(`Normalizing chat ID: ${chat.id} -> ${normalizedId}`);
  
  // Проверяем, не является ли это супергруппой, которую нужно игнорировать
  const { data: shouldIgnore } = await supabase
    .rpc('should_ignore_telegram_supergroup', { supergroup_id: normalizedId });
  
  if (shouldIgnore) {
    console.log('Ignoring deleted/test supergroup:', normalizedId);
    return null;
  }

  // Check for and remove any duplicate with non-normalized ID
  if (chat.id !== normalizedId) {
    console.log(`Checking for duplicate with original ID: ${chat.id}`);
    const { error: deleteError } = await supabase
      .from('telegram_supergroups')
      .delete()
      .eq('id', chat.id);
    
    if (deleteError) {
      console.warn('Failed to delete potential duplicate:', deleteError);
    } else {
      console.log('Removed potential duplicate supergroup');
    }
  }

  // Проверяем, есть ли уже эта супергруппа
  const { data: existingSupergroup } = await supabase
    .from('telegram_supergroups')
    .select('*')
    .eq('id', normalizedId)
    .single();

  if (existingSupergroup) {
    // Обновляем информацию о группе
    const { data: updatedSupergroup } = await supabase
      .from('telegram_supergroups')
      .update({
        title: chat.title,
        username: chat.username,
        description: chat.description,
        invite_link: chat.invite_link,
        is_forum: chat.is_forum || false, // Обновляем is_forum
        updated_at: new Date().toISOString(),
        metadata: {
          permissions: chat.permissions,
          slow_mode_delay: chat.slow_mode_delay,
          message_auto_delete_time: chat.message_auto_delete_time,
          has_protected_content: chat.has_protected_content,
        }
      })
      .eq('id', normalizedId)
      .select()
      .single();

    return updatedSupergroup;
  } else {
    // Создаем новую супергруппу
    const { data: newSupergroup } = await supabase
      .from('telegram_supergroups')
      .insert({
        id: normalizedId,
        title: chat.title || 'Untitled Group',
        username: chat.username,
        description: chat.description,
        invite_link: chat.invite_link,
        is_forum: chat.is_forum || false,
        metadata: {
          permissions: chat.permissions,
          slow_mode_delay: chat.slow_mode_delay,
          message_auto_delete_time: chat.message_auto_delete_time,
          has_protected_content: chat.has_protected_content,
        }
      })
      .select()
      .single();

    console.log('Created new supergroup:', newSupergroup);
    return newSupergroup;
  }
}

// Функция для получения или создания чата для темы/общего чата
async function ensureChatExists(supergroup: any, topicId?: number, topicName?: string, isTopicMessage?: boolean) {
  // Для форумных групп проверяем, что это реально сообщение в топике
  if (supergroup.is_forum && topicId && topicId !== 1 && !isTopicMessage && !topicName) {
    // Сообщение пришло с message_thread_id, но без is_topic_message=true
    // Это может быть "фантомный" топик - сохраняем в General с metadata
    console.log(`Warning: Message with thread_id=${topicId} but not marked as topic message. Treating as General.`);
    topicId = 1;
  }
  
  // Нормализуем topicId для форумных групп: если null/undefined, используем 1 для General
  const normalizedTopicId = (supergroup.is_forum && !topicId) ? 1 : topicId;
  
  let chatName: string;
  let isGeneral = false;
  
  if (normalizedTopicId === 1 && supergroup.is_forum) {
    // Это General топик - называем по компании или супергруппе
    isGeneral = true;
    if (supergroup.company_id) {
      // Получаем название компании
      const { data: company } = await supabase
        .from('companies')
        .select('name')
        .eq('id', supergroup.company_id)
        .single();
      
      chatName = company?.name || supergroup.title;
    } else {
      chatName = supergroup.title;
    }
  } else {
    chatName = normalizedTopicId 
      ? (topicName || `${supergroup.title} - Topic ${normalizedTopicId}`)
      : supergroup.title;
  }

  console.log('Ensuring chat exists for supergroup:', supergroup.id, 'topic:', normalizedTopicId);

  // Ищем существующий чат - используем робастную логику для General
  let existingChat = null;
  
  if (normalizedTopicId === 1 && supergroup.is_forum) {
    // Для General чата ищем в следующем порядке приоритета:
    // 1. is_active = true AND telegram_topic_id = 1
    // 2. is_active = true AND telegram_topic_id IS NULL  
    // 3. любой с topic_id = 1
    // 4. любой с topic_id IS NULL
    
    const searchVariants = [
      { topic_id: 1, is_active: true },
      { topic_id: null, is_active: true },
      { topic_id: 1, is_active: null },
      { topic_id: null, is_active: null }
    ];
    
    for (const variant of searchVariants) {
      let query = supabase
        .from('chats')
        .select('*')
        .eq('telegram_supergroup_id', supergroup.id)
        .order('created_at', { ascending: true }); // Берем самый ранний
      
      if (variant.topic_id !== null) {
        query = query.eq('telegram_topic_id', variant.topic_id);
      } else {
        query = query.is('telegram_topic_id', null);
      }
      
      if (variant.is_active !== null) {
        query = query.eq('is_active', variant.is_active);
      }
      
      const { data: chats, error } = await query.limit(10); // Лимит для безопасности
      
      if (error) {
        console.error('Error searching for General chat:', error);
        continue;
      }
      
      if (chats && chats.length > 0) {
        existingChat = chats[0]; // Берем первый (самый ранний)
        console.log(`Found General chat using variant ${JSON.stringify(variant)}: ${existingChat.id} (found ${chats.length} total)`);
        break;
      }
    }
  } else {
    // Для обычных топиков - стандартный поиск
    let query = supabase
      .from('chats')
      .select('*')
      .eq('telegram_supergroup_id', supergroup.id)
      .eq('is_active', true) // Только активные
      .order('created_at', { ascending: true });

    if (normalizedTopicId) {
      query = query.eq('telegram_topic_id', normalizedTopicId);
    } else {
      query = query.is('telegram_topic_id', null);
    }

    const { data: chats, error } = await query.limit(1);
    
    if (error) {
      console.error('Error finding existing chat:', error);
    } else if (chats && chats.length > 0) {
      existingChat = chats[0];
      console.log('Found existing chat:', existingChat.id);
    }
  }

  if (existingChat) {
    // Проверяем, нужно ли обновить имя чата
    let shouldUpdateName = false;
    
    if (topicName && existingChat.name !== chatName) {
      // Обновляем имя, если есть новое имя топика
      shouldUpdateName = true;
    } else if (normalizedTopicId === 1 && supergroup.is_forum && supergroup.company_id) {
      // Для General-чата проверяем, совпадает ли имя с названием компании
      const { data: company } = await supabase
        .from('companies')
        .select('name')
        .eq('id', supergroup.company_id)
        .single();
      
      if (company && existingChat.name !== company.name) {
        chatName = company.name;
        shouldUpdateName = true;
      }
    }
    
    if (shouldUpdateName) {
      console.log(`Updating chat name from "${existingChat.name}" to "${chatName}"`);
      const { data: updatedChat } = await supabase
        .from('chats')
        .update({ 
          name: chatName, 
          updated_at: new Date().toISOString(),
          metadata: {
            ...existingChat.metadata,
            is_general: isGeneral
          }
        })
        .eq('id', existingChat.id)
        .select()
        .single();
      return updatedChat || existingChat;
    }
    
    return existingChat;
  }

  // Создаем новый чат только если ничего не найдено
  console.log('Creating new chat for Telegram supergroup');

  const { data: newChat, error: insertError } = await supabase
    .from('chats')
    .insert({
      name: chatName,
      type: 'telegram_group',
      telegram_supergroup_id: supergroup.id,
      telegram_topic_id: normalizedTopicId || null,
      telegram_sync: true,
      created_by: null, // Telegram чаты создаются автоматически, без конкретного пользователя
      company_id: supergroup.company_id,
      metadata: {
        telegram_chat_id: supergroup.id,
        telegram_topic_id: normalizedTopicId,
        source: 'telegram_webhook',
        is_general: isGeneral,
        topic_verified: topicName ? true : (normalizedTopicId === 1 ? true : false), // Only verified if we have topic name or it's General
        created_from_forum_event: !!topicName
      }
    })
    .select()
    .single();

  if (insertError) {
    console.error('Error creating new chat:', insertError);
    throw insertError;
  }

  console.log('Successfully created new chat:', newChat?.id);
  return newChat;
}

// Функция для обновления участника группы
async function updateGroupMember(supergroupId: number, user: TelegramMessage['from']) {
  const { data: member } = await supabase
    .from('telegram_group_members')
    .upsert({
      supergroup_id: supergroupId,
      telegram_user_id: user.id,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      is_bot: user.is_bot,
      last_seen: new Date().toISOString(),
      metadata: {
        language_code: user.language_code,
      }
    }, {
      onConflict: 'supergroup_id,telegram_user_id'
    })
    .select()
    .single();

  return member;
}

// Функция для определения типа сообщения
function getMessageType(message: TelegramMessage): string {
  if (message.text) return 'text';
  if (message.photo) return 'photo';
  if (message.video) return 'video';
  if (message.document) return 'document';
  if (message.audio) return 'audio';
  if (message.voice) return 'voice';
  if (message.sticker) return 'sticker';
  return 'other';
}

// Normalize message type for database storage
function normalizeMessageType(telegramType: string): string {
  switch (telegramType) {
    case 'photo': return 'image';
    case 'document': return 'file';
    case 'video': return 'video';
    case 'audio': return 'file';
    case 'voice': return 'voice';
    case 'text': return 'text';
    default: return 'file';
  }
}

// Download file from Telegram and upload to Supabase Storage with improved error handling
async function downloadAndStoreFile(
  fileId: string, 
  fileName: string, 
  mimeType: string,
  supergroupId: number,
  topicId: number | null,
  messageId: number
): Promise<{ url: string | null, status: 'stored' | 'proxy', filePath?: string }> {
  const telegramBotToken = getBotToken();
  if (!telegramBotToken) {
    console.error('Telegram bot token not configured');
    // Return proxy URL as fallback
    const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_id=${fileId}`;
    return { url: proxyUrl, status: 'proxy' };
  }

  try {
    // Get file path from Telegram
    const fileResponse = await fetch(`https://api.telegram.org/bot${telegramBotToken}/getFile?file_id=${fileId}`);
    const fileData = await fileResponse.json();
    
    if (!fileData.ok) {
      console.error('Failed to get file info from Telegram:', fileData);
      const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_id=${fileId}`;
      return { url: proxyUrl, status: 'proxy' };
    }

    const telegramFilePath = fileData.result.file_path;
    
    // Download file from Telegram
    const downloadResponse = await fetch(`https://api.telegram.org/file/bot${telegramBotToken}/${telegramFilePath}`);
    if (!downloadResponse.ok) {
      console.error('Failed to download file from Telegram');
      const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_path=${encodeURIComponent(telegramFilePath)}`;
      return { url: proxyUrl, status: 'proxy', filePath: telegramFilePath };
    }

    const fileBuffer = await downloadResponse.arrayBuffer();
    
    // Generate organized path: tg/{supergroup_id}/{topic_id}/{yyyy}/{mm}/{message_id}_{safe_filename}
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const safeName = fileName.replace(/[^a-zA-Z0-9._-]/g, '_');
    const topicPath = topicId ? topicId : 'general';
    const storagePath = `tg/${supergroupId}/${topicPath}/${year}/${month}/${messageId}_${safeName}`;
    
    // Upload to Supabase Storage
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('chat-files')
      .upload(storagePath, fileBuffer, {
        contentType: mimeType || 'application/octet-stream',
        cacheControl: '3600'
      });

    if (uploadError) {
      console.error('Failed to upload file to storage:', uploadError);
      // Fallback to proxy URL
      const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_path=${encodeURIComponent(telegramFilePath)}`;
      return { url: proxyUrl, status: 'proxy', filePath: telegramFilePath };
    }

    // Get public URL
    const { data: urlData } = supabase.storage
      .from('chat-files')
      .getPublicUrl(uploadData.path);

    console.log(`Successfully uploaded file to storage: ${uploadData.path}`);
    return { url: urlData.publicUrl, status: 'stored', filePath: telegramFilePath };

  } catch (error) {
    console.error('Error downloading and storing file:', error);
    // Fallback to proxy URL
    const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_id=${fileId}`;
    return { url: proxyUrl, status: 'proxy' };
  }
}

// Функция для сохранения сообщения в базу данных
async function saveMessage(message: TelegramMessage, chat: any, supergroup: any) {
  // Check if this message already exists (prevent duplicates from bot messages)
  const { data: existingMessage } = await supabase
    .from('messages')
    .select('id')
    .eq('telegram_message_id', message.message_id)
    .eq('chat_id', chat.id)
    .single();
  
  if (existingMessage) {
    console.log('Message already exists, skipping duplicate:', message.message_id);
    return existingMessage;
  }

  const messageType = getMessageType(message);
  let content = message.text || message.caption || '';
  let fileUrl = null;
  let fileName = null;
  let fileType = null;
  let fileSize = null;
  let fileId = null;
  let telegramFileId = null;
  let telegramFilePath = null;
  let fileStatus = 'stored';

  // Handle media files with improved logic
  if (message.photo && message.photo.length > 0) {
    const largestPhoto = message.photo[message.photo.length - 1];
    fileType = 'image/jpeg';
    fileSize = largestPhoto.file_size;
    telegramFileId = largestPhoto.file_id;
    fileName = `photo_${largestPhoto.file_id}.jpg`;
    
    // Download and store the photo
    const result = await downloadAndStoreFile(
      telegramFileId, 
      fileName, 
      fileType,
      supergroup.id,
      message.message_thread_id,
      message.message_id
    );
    fileUrl = result.url;
    fileStatus = result.status;
    telegramFilePath = result.filePath;
  } else if (message.document) {
    fileType = message.document.mime_type;
    fileSize = message.document.file_size;
    telegramFileId = message.document.file_id;
    fileName = message.document.file_name || `document_${message.document.file_id}`;
    
    // Download and store the document
    const result = await downloadAndStoreFile(
      telegramFileId, 
      fileName, 
      fileType,
      supergroup.id,
      message.message_thread_id,
      message.message_id
    );
    fileUrl = result.url;
    fileStatus = result.status;
    telegramFilePath = result.filePath;
  } else if (message.video) {
    fileType = message.video.mime_type || 'video/mp4';
    fileSize = message.video.file_size;
    telegramFileId = message.video.file_id;
    fileName = `video_${message.video.file_id}.mp4`;
    
    // Download and store the video
    const result = await downloadAndStoreFile(
      telegramFileId, 
      fileName, 
      fileType,
      supergroup.id,
      message.message_thread_id,
      message.message_id
    );
    fileUrl = result.url;
    fileStatus = result.status;
    telegramFilePath = result.filePath;
  } else if (message.audio) {
    fileType = message.audio.mime_type || 'audio/mpeg';
    fileSize = message.audio.file_size;
    telegramFileId = message.audio.file_id;
    fileName = message.audio.file_name || `audio_${message.audio.file_id}.mp3`;
    
    // Download and store the audio
    const result = await downloadAndStoreFile(
      telegramFileId, 
      fileName, 
      fileType,
      supergroup.id,
      message.message_thread_id,
      message.message_id
    );
    fileUrl = result.url;
    fileStatus = result.status;
    telegramFilePath = result.filePath;
  } else if (message.voice) {
    fileType = 'audio/ogg';
    fileSize = message.voice.file_size;
    telegramFileId = message.voice.file_id;
    fileName = `voice_${message.voice.file_id}.ogg`;
    
    // Download and store the voice message
    const result = await downloadAndStoreFile(
      telegramFileId, 
      fileName, 
      fileType,
      supergroup.id,
      message.message_thread_id,
      message.message_id
    );
    fileUrl = result.url;
    fileStatus = result.status;
    telegramFilePath = result.filePath;
  }

  if (fileId && !fileUrl) {
    console.error(`Failed to download and store file: ${fileId}`);
  }

  // Обработка пересланных сообщений
  let forwardData = null;
  if (message.forward_from || message.forward_from_chat) {
    forwardData = {
      forward_from: message.forward_from,
      forward_from_chat: message.forward_from_chat,
      forward_from_message_id: message.forward_from_message_id,
      forward_signature: message.forward_signature,
      forward_sender_name: message.forward_sender_name,
      forward_date: message.forward_date,
    };
  }

  // Правильная обработка reply_to_id: находим сообщение в нашей базе по telegram_message_id
  let replyToId = null;
  let replyMetadata = null;
  
  if (message.reply_to_message) {
    console.log('Processing reply to telegram message:', message.reply_to_message.message_id);
    
    // Ищем существующее сообщение в нашей базе по telegram_message_id и chat_id
    const { data: replyToMessage } = await supabase
      .from('messages')
      .select('id')
      .eq('telegram_message_id', message.reply_to_message.message_id)
      .eq('chat_id', chat.id)
      .single();
    
    if (replyToMessage) {
      replyToId = replyToMessage.id;
      console.log('Found existing message for reply:', replyToMessage.id);
    } else {
      console.log('Reply message not found in our database, storing in metadata');
      // Сохраняем информацию о reply в metadata
      replyMetadata = {
        telegram_reply_to_message_id: message.reply_to_message.message_id,
        telegram_reply_user: message.reply_to_message.from,
        telegram_reply_text: message.reply_to_message.text || message.reply_to_message.caption
      };
    }
  }

  // Нормализуем topic_id для сообщений: если null/undefined в форумной группе, используем 1
  const normalizedMessageTopicId = (supergroup.is_forum && !message.message_thread_id) ? 1 : message.message_thread_id;
  
  // Сохраняем информацию о потенциально удаленном топике в metadata
  let phantomTopicInfo = null;
  if (supergroup.is_forum && message.message_thread_id && message.message_thread_id !== 1 && !message.is_topic_message && !topicName) {
    phantomTopicInfo = {
      original_thread_id: message.message_thread_id,
      likely_phantom_topic: true,
      moved_to_general: true
    };
  }

  const { data: savedMessage, error } = await supabase
    .from('messages')
    .insert({
      chat_id: chat.id,
      telegram_message_id: message.message_id,
      telegram_user_id: message.from.id,
      telegram_user_data: {
        id: message.from.id,
        first_name: message.from.first_name,
        last_name: message.from.last_name,
        username: message.from.username,
        is_bot: message.from.is_bot,
      },
      telegram_topic_id: normalizedMessageTopicId,
      content: content,
      message_type: messageType,
      file_url: fileUrl,
      file_name: fileName,
      file_type: fileType,
      file_size: fileSize,
      telegram_file_id: telegramFileId,
      telegram_file_path: telegramFilePath,
      file_status: fileStatus,
      telegram_forward_data: forwardData,
      sync_direction: 'telegram_to_web',
      reply_to_id: replyToId,
      metadata: {
        telegram_entities: message.entities,
        telegram_date: message.date,
        raw_message: message,
        ...replyMetadata,
        ...phantomTopicInfo
      }
    })
    .select()
    .single();

  if (error) {
    console.error('Error saving message:', error);
    throw error;
  }

  console.log('Saved message:', savedMessage.id, 'with file status:', fileStatus);
  return savedMessage;
}

// Основная функция обработки webhook
async function processUpdate(update: TelegramUpdate) {
  const message = update.message || update.edited_message || update.channel_post || update.edited_channel_post;
  
  if (!message) {
    console.log('No message in update, skipping');
    return;
  }

  // Extract topic name from forum events
  let topicName: string | undefined;
  if (message.forum_topic_created) {
    topicName = message.forum_topic_created.name;
    console.log('Forum topic created:', topicName);
  } else if (message.forum_topic_edited && message.forum_topic_edited.name) {
    topicName = message.forum_topic_edited.name;
    console.log('Forum topic edited:', topicName);
  } else if (message.reply_to_message?.forum_topic_created?.name) {
    // Извлекаем имя топика из reply_to_message если прямого события нет
    topicName = message.reply_to_message.forum_topic_created.name;
    console.log('Topic name from reply_to_message.forum_topic_created:', topicName);
  } else if (message.reply_to_message?.forum_topic_edited?.name) {
    // Извлекаем имя топика из reply_to_message если это было изменено
    topicName = message.reply_to_message.forum_topic_edited.name;
    console.log('Topic name from reply_to_message.forum_topic_edited:', topicName);
  }

  console.log('Processing message:', {
    messageId: message.message_id,
    chatId: message.chat.id,
    chatType: message.chat.type,
    topicId: message.message_thread_id,
    topicName: topicName,
    messageType: getMessageType(message)
  });

  // Обрабатываем только супергруппы и группы
  if (message.chat.type !== 'supergroup' && message.chat.type !== 'group') {
    console.log('Not a supergroup/group, skipping');
    return;
  }

  try {
    // 1. Убеждаемся, что супергруппа существует в базе данных
    const supergroup = await ensureSupergroupExists(message.chat);
    if (!supergroup) {
      console.log('Failed to ensure supergroup exists');
      return;
    }

    // 2. Обновляем участника группы
    await updateGroupMember(supergroup.id, message.from);

    // 3. Убеждаемся, что чат для темы/общего чата существует
    const chat = await ensureChatExists(supergroup, message.message_thread_id, topicName, message.is_topic_message);
    if (!chat) {
      console.log('Failed to ensure chat exists');
      return;
    }

    // 4. Сохраняем сообщение
    await saveMessage(message, chat, supergroup);

    console.log('Successfully processed update');
  } catch (error) {
    console.error('Error processing update:', error);
    throw error;
  }
}

serve(async (req) => {
  console.log(`${req.method} ${req.url}`);

  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // Security: Validate webhook secret
  if (telegramWebhookSecret) {
    const providedSecret = req.headers.get('X-Telegram-Bot-Api-Secret-Token');
    if (!providedSecret || providedSecret !== telegramWebhookSecret) {
      console.error('Invalid webhook secret');
      return new Response('Unauthorized', { 
        status: 401, 
        headers: corsHeaders 
      });
    }
  }

  try {
    if (req.method !== 'POST') {
      return new Response('Method not allowed', { 
        status: 405, 
        headers: corsHeaders 
      });
    }

    const update: TelegramUpdate = await req.json();
    console.log('Received update:', JSON.stringify(update, null, 2));

    // Обрабатываем обновление
    await processUpdate(update);

    return new Response(JSON.stringify({ ok: true }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Webhook error:', error);
    
    return new Response(JSON.stringify({ 
      error: 'Internal server error', 
      details: error instanceof Error ? error.message : 'Unknown error'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
