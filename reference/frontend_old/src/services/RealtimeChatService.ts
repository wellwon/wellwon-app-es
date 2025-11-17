import { supabase } from '@/integrations/supabase/client';
import type { Chat, Message, TypingIndicator, MessageRead } from '@/types/realtime-chat';
import type { RealtimeChannel } from '@supabase/supabase-js';
import { logger } from '@/utils/logger';
import { TelegramChatService } from './TelegramChatService';

class RealtimeChatService {
  private subscriptions: Map<string, RealtimeChannel> = new Map();
  private chatsSubscription: RealtimeChannel | null = null;

  // Получение чатов пользователя с фильтрацией по компании
  async getUserChats(userId: string, companyId?: number): Promise<Chat[]> {
    logger.info('Loading chats for user', { userId, companyId, component: 'RealtimeChatService' });
    
    // Используем новую функцию для получения чатов с фильтрацией по компании
    const { data, error } = await supabase.rpc('get_user_chats_by_company', {
      user_uuid: userId,
      company_uuid: companyId || null
    });

    if (error) {
      logger.error('Error loading chats', error, { component: 'RealtimeChatService', userId, companyId });
      throw error;
    }

    logger.debug('Loaded chats from function', { count: data?.length || 0, component: 'RealtimeChatService' });
    
    // Загружаем дополнительные данные для чатов
    const chatIds = data?.map(chat => chat.id) || [];
    if (chatIds.length === 0) {
      return [];
    }

    // Получаем участников и последние сообщения
    const { data: chatsWithDetails, error: detailsError } = await supabase
      .from('chats')
      .select(`
        *,
        participants:chat_participants(
          user_id,
          role,
          last_read_at,
          is_active
        ),
        last_message:messages(
          id,
          content,
          message_type,
          created_at,
          sender_id
        )
      `)
      .in('id', chatIds)
      .eq('is_active', true)
      .order('updated_at', { ascending: false });

    if (detailsError) {
      logger.error('Error loading chat details', detailsError, { component: 'RealtimeChatService' });
      throw detailsError;
    }

    logger.debug('Loaded chats with details', { count: chatsWithDetails?.length || 0, component: 'RealtimeChatService' });
    return await this.transformChatsWithCounts(chatsWithDetails || [], userId);
  }

  // Получение архивных чатов пользователя по супергруппе
  async getArchivedChatsBySupergroup(userId: string, supergroupId: number): Promise<Chat[]> {
    logger.info('Loading archived chats for user by supergroup', { userId, supergroupId, component: 'RealtimeChatService' });
    
    const { data, error } = await supabase.rpc('get_user_chats_by_supergroup_archived', {
      user_uuid: userId,
      supergroup_id_param: supergroupId
    });

    if (error) {
      logger.error('Error loading archived chats by supergroup', error, { component: 'RealtimeChatService', userId, supergroupId });
      throw error;
    }

    logger.debug('Loaded archived chats from supergroup function', { count: data?.length || 0, component: 'RealtimeChatService' });
    
    // Загружаем дополнительные данные для чатов
    const chatIds = data?.map(chat => chat.id) || [];
    if (chatIds.length === 0) {
      return [];
    }

    // Получаем участников и последние сообщения для архивных чатов
    const { data: chatsWithDetails, error: detailsError } = await supabase
      .from('chats')
      .select(`
        *,
        participants:chat_participants(
          user_id,
          role,
          last_read_at,
          is_active
        ),
        last_message:messages(
          id,
          content,
          message_type,
          created_at,
          sender_id
        )
      `)
      .in('id', chatIds)
      .eq('is_active', false) // Только неактивные (архивные) чаты
      .order('telegram_topic_id', { ascending: true, nullsFirst: false })
      .order('updated_at', { ascending: false });

    if (detailsError) {
      logger.error('Error loading archived chat details for supergroup', detailsError, { component: 'RealtimeChatService' });
      throw detailsError;
    }

    logger.debug('Loaded archived supergroup chats with details', { count: chatsWithDetails?.length || 0, component: 'RealtimeChatService' });
    return await this.transformChatsWithCounts(chatsWithDetails || [], userId);
  }

  // Получение чатов пользователя с фильтрацией по супергруппе
  async getUserChatsBySupergroup(userId: string, supergroupId: number): Promise<Chat[]> {
    logger.info('Loading chats for user by supergroup', { userId, supergroupId, component: 'RealtimeChatService' });
    
    const { data, error } = await supabase.rpc('get_user_chats_by_supergroup', {
      user_uuid: userId,
      supergroup_id_param: supergroupId
    });

    if (error) {
      logger.error('Error loading chats by supergroup', error, { component: 'RealtimeChatService', userId, supergroupId });
      throw error;
    }

    logger.debug('Loaded chats from supergroup function', { count: data?.length || 0, component: 'RealtimeChatService' });
    
    // Загружаем дополнительные данные для чатов
    const chatIds = data?.map(chat => chat.id) || [];
    if (chatIds.length === 0) {
      return [];
    }

    // Получаем участников и последние сообщения
    const { data: chatsWithDetails, error: detailsError } = await supabase
      .from('chats')
      .select(`
        *,
        participants:chat_participants(
          user_id,
          role,
          last_read_at,
          is_active
        ),
        last_message:messages(
          id,
          content,
          message_type,
          created_at,
          sender_id
        )
      `)
      .in('id', chatIds)
      .eq('is_active', true)
      .order('telegram_topic_id', { ascending: true, nullsFirst: false })
      .order('updated_at', { ascending: false });

    if (detailsError) {
      logger.error('Error loading chat details for supergroup', detailsError, { component: 'RealtimeChatService' });
      throw detailsError;
    }

    logger.debug('Loaded supergroup chats with details', { count: chatsWithDetails?.length || 0, component: 'RealtimeChatService' });
    return await this.transformChatsWithCounts(chatsWithDetails || [], userId);
  }

  // Создание нового чата с автоматической привязкой к компании
  async createChat(name: string, type: Chat['type'], createdBy: string, participantIds?: string[], companyId?: number): Promise<Chat> {
    logger.info('Creating chat', { name, type, createdBy, participantIds, companyId, component: 'RealtimeChatService' });
    
    // Используем новую функцию для создания чата с компанией
    const { data: chatId, error } = await supabase.rpc('create_chat_with_company', {
      chat_name: name,
      chat_type: type,
      creator_id: createdBy,
      company_uuid: companyId || null
    });

    if (error) {
      logger.error('Error creating chat', error, { component: 'RealtimeChatService', name, type });
      throw error;
    }

    logger.info('Chat created successfully', { chatId, component: 'RealtimeChatService' });
    
    // Добавляем дополнительных участников если есть
    if (participantIds && participantIds.length > 0) {
      await this.addParticipantsToChat(chatId, participantIds);
    }

    // Получаем созданный чат
    const { data: chatData, error: fetchError } = await supabase
      .from('chats')
      .select('*')
      .eq('id', chatId)
      .single();

    if (fetchError) {
      logger.error('Error fetching created chat', fetchError, { component: 'RealtimeChatService', chatId });
      throw fetchError;
    }

    return {
      id: chatData.id,
      company_id: chatData.company_id,
      created_by: chatData.created_by,
      created_at: chatData.created_at,
      updated_at: chatData.updated_at,
      is_active: chatData.is_active,
      metadata: (chatData.metadata as Record<string, any>) || {},
      name: chatData.name,
      type: chatData.type as Chat['type'],
      participants: [],
      last_message: null,
      unread_count: 0
    };
  }

  // Добавление участников в чат
  async addParticipants(chatId: string, userIds: string[]): Promise<void> {
    await this.addParticipantsToChat(chatId, userIds);
  }

  async addParticipantsToChat(chatId: string, userIds: string[]): Promise<void> {
    const participants = userIds.map(userId => ({
      chat_id: chatId,
      user_id: userId,
      role: 'member'
    }));

    const { error } = await supabase
      .from('chat_participants')
      .insert(participants);

    if (error) throw error;
  }

  // Получение метаданных сообщения по ID
  async getMessageMeta(messageId: string): Promise<{ created_at: string; chat_id: string } | null> {
    logger.debug('Getting message meta', { messageId, component: 'RealtimeChatService' });
    
    const { data, error } = await supabase
      .from('messages')
      .select('created_at, chat_id')
      .eq('id', messageId)
      .or('is_deleted.is.false,is_deleted.is.null')
      .single();

    if (error) {
      logger.error('Error getting message meta', error, { component: 'RealtimeChatService', messageId });
      return null;
    }

    return data;
  }

  // Подсчет сообщений новее указанной даты
  async countMessagesNewerThan(chatId: string, timestamp: string): Promise<number> {
    logger.debug('Counting messages newer than timestamp', { chatId, timestamp, component: 'RealtimeChatService' });
    
    const { count, error } = await supabase
      .from('messages')
      .select('*', { count: 'exact', head: true })
      .eq('chat_id', chatId)
      .or('is_deleted.is.false,is_deleted.is.null')
      .gt('created_at', timestamp);

    if (error) {
      logger.error('Error counting newer messages', error, { component: 'RealtimeChatService', chatId, timestamp });
      return 0;
    }

    return count || 0;
  }

  // Получение сообщений чата
  async getChatMessages(chatId: string, limit: number = 20, offset: number = 0): Promise<Message[]> {
    logger.debug('Loading messages for chat', { chatId, limit, offset, component: 'RealtimeChatService' });
    
    // Для правильной пагинации: берем последние сообщения при offset=0, старые при offset>0
    const { data, error } = await supabase
      .from('messages')
      .select(`
        *,
        reply_to:messages!reply_to_id(
          id,
          content,
          message_type,
          file_name,
          file_url,
          voice_duration,
          created_at,
          sender_id,
          telegram_user_data
        )
      `)
      .eq('chat_id', chatId)
      .or('is_deleted.is.false,is_deleted.is.null')
      .order('created_at', { ascending: false }) // Сначала новые
      .range(offset, offset + limit - 1);

    if (error) {
      logger.error('Error loading messages', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }

    logger.debug('Loaded messages', { count: data?.length || 0, chatId, component: 'RealtimeChatService' });
    
    // Загружаем профили отправителей отдельно
    const senderIds = [...new Set(data?.map(msg => msg.sender_id).filter(Boolean) || [])];
    const replyToSenderIds = [...new Set(data?.map(msg => msg.reply_to?.sender_id).filter(Boolean) || [])];
    const allSenderIds = [...new Set([...senderIds, ...replyToSenderIds])];
    
    let profiles: Record<string, any> = {};
    let tgUsers: Record<number, any> = {};
    
    // Загружаем профили платформы
    if (allSenderIds.length > 0) {
      const { data: profilesData } = await supabase
        .from('profiles')
        .select('user_id, first_name, last_name, avatar_url, developer, role_label')
        .in('user_id', allSenderIds);
      
      profiles = (profilesData || []).reduce((acc, profile) => {
        acc[profile.user_id] = profile;
        return acc;
      }, {} as Record<string, any>);
    }
    
    // Загружаем роли Telegram пользователей
    const telegramUserIds = [...new Set(data?.map(msg => msg.telegram_user_id).filter(Boolean) || [])];
    if (telegramUserIds.length > 0) {
      const { data: tgUsersData } = await supabase
        .from('tg_users')
        .select('id, role_label')
        .in('id', telegramUserIds);
      
      tgUsers = (tgUsersData || []).reduce((acc, tgUser) => {
        acc[tgUser.id] = tgUser;
        return acc;
      }, {} as Record<number, any>);
    }
    
    // Преобразуем сообщения с загруженными профилями и ролями
    const transformedMessages: Message[] = (data || []).map(msg => {
      // Определяем роль пользователя
      let roleLabel = 'Нет роли';
      if (profiles[msg.sender_id]?.role_label) {
        roleLabel = profiles[msg.sender_id].role_label;
      } else if (msg.telegram_user_id && tgUsers[msg.telegram_user_id]?.role_label) {
        roleLabel = tgUsers[msg.telegram_user_id].role_label;
      }
      
      // Add backward compatibility mapping for old message types
      let messageType = msg.message_type;
      if (messageType === 'photo') messageType = 'image';
      else if (messageType === 'document') messageType = 'file';
      
      return {
        id: msg.id,
        chat_id: msg.chat_id,
        sender_id: msg.sender_id,
        content: msg.content,
        message_type: messageType as Message['message_type'],
        file_url: msg.file_url,
        file_name: msg.file_name,
        file_type: msg.file_type,
        file_size: msg.file_size,
        voice_duration: msg.voice_duration,
        reply_to_id: msg.reply_to_id,
        interactive_data: (msg as any).interactive_data,
        created_at: msg.created_at,
        updated_at: msg.updated_at,
        is_edited: msg.is_edited,
        is_deleted: msg.is_deleted,
        metadata: {
          ...(msg.metadata as Record<string, any>) || {},
          role_label: roleLabel
        },
        sender_profile: profiles[msg.sender_id] || null,
        // Telegram fields
        telegram_message_id: msg.telegram_message_id,
        telegram_user_id: msg.telegram_user_id,
        telegram_user_data: msg.telegram_user_data as any,
        telegram_topic_id: msg.telegram_topic_id,
        telegram_forward_data: msg.telegram_forward_data as any,
        sync_direction: msg.sync_direction as any,
        reply_to: (() => {
          // Безопасная нормализация reply_to данных
          if (!msg.reply_to_id) return null;
          
          let replyData = msg.reply_to;
          
          // Если reply_to массив, берем первый элемент
          if (Array.isArray(replyData)) {
            replyData = replyData[0];
          }
          
          // Если нет данных или пустой объект, возвращаем fallback
          if (!replyData || typeof replyData !== 'object' || Object.keys(replyData).length === 0) {
            return {
              id: msg.reply_to_id,
              chat_id: chatId,
              sender_id: null,
              content: null,
              message_type: 'text' as Message['message_type'],
              file_url: null,
              file_name: null,
              file_type: null,
              file_size: null,
              voice_duration: null,
              reply_to_id: null,
              interactive_data: null,
              created_at: msg.created_at,
              updated_at: msg.created_at,
              is_edited: false,
              is_deleted: false,
              metadata: {},
              sender_profile: null,
              telegram_user_data: null,
              reply_to: null,
              read_by: []
            };
          }
          
          return {
            id: replyData.id || msg.reply_to_id,
            chat_id: chatId,
            sender_id: replyData.sender_id,
            content: replyData.content,
            message_type: (replyData.message_type || 'text') as Message['message_type'],
            file_url: replyData.file_url,
            file_name: replyData.file_name,
            file_type: null,
            file_size: null,
            voice_duration: replyData.voice_duration,
            reply_to_id: null,
            interactive_data: (replyData as any).interactive_data,
            created_at: replyData.created_at || msg.created_at,
            updated_at: replyData.created_at || msg.created_at,
            is_edited: false,
            is_deleted: false,
            metadata: {},
            sender_profile: profiles[replyData.sender_id] || null,
            telegram_user_data: replyData.telegram_user_data as any,
            reply_to: null,
            read_by: []
          };
        })(),
        read_by: []
      };
    });

    return transformedMessages;
  }

  // Получение отфильтрованных сообщений чата по типу
  async getChatMessagesFiltered(chatId: string, filter: string, limit: number = 20, offset: number = 0): Promise<Message[]> {
    logger.debug('Loading filtered messages for chat', { chatId, filter, limit, offset, component: 'RealtimeChatService' });
    
    let query = supabase
      .from('messages')
      .select(`
        *,
        reply_to:messages!reply_to_id(
          id,
          content,
          message_type,
          file_name,
          file_url,
          voice_duration,
          created_at,
          sender_id,
          telegram_user_data
        )
      `)
      .eq('chat_id', chatId)
      .or('is_deleted.is.false,is_deleted.is.null');

    // Применяем фильтры как в клиентском коде
    switch (filter) {
      case 'images':
        // Поддержка legacy типов: 'image' и 'photo', но только если есть file_url
        query = query.in('message_type', ['image', 'photo'])
          .not('file_url', 'is', null);
        break;
      case 'voice':
        query = query.eq('message_type', 'voice');
        break;
      case 'pdf':
        // Проверяем как file_name, так и file_url на расширение .pdf
        query = query.in('message_type', ['file', 'document'])
          .or('file_name.ilike.%.pdf,file_url.ilike.%.pdf');
        break;
      case 'doc':
        // Файлы .doc/.docx (в file_name или file_url) ИЛИ текст/интерактивные с Google Docs ссылками
        query = query.or(`and(message_type.in.(file,document),or(file_name.ilike.%.doc,file_name.ilike.%.docx,file_url.ilike.%.doc,file_url.ilike.%.docx)),and(message_type.in.(text,interactive),content.ilike.%docs.google.com/document%)`);
        break;
      case 'xls':
        // Файлы .xls/.xlsx (в file_name или file_url) ИЛИ текст/интерактивные с Google Sheets ссылками
        query = query.or(`and(message_type.in.(file,document),or(file_name.ilike.%.xls,file_name.ilike.%.xlsx,file_url.ilike.%.xls,file_url.ilike.%.xlsx)),and(message_type.in.(text,interactive),or(content.ilike.%docs.google.com/spreadsheets%,content.ilike.%sheets.google.com%))`);
        break;
      case 'other':
        // Файлы (file/document) с именем файла ИЛИ URL, НО исключаем известные расширения
        query = query.in('message_type', ['file', 'document'])
          .or('file_name.not.is.null,file_url.not.is.null') // Хотя бы одно из полей заполнено
          .not('file_name', 'ilike', '%.pdf')
          .not('file_name', 'ilike', '%.doc')
          .not('file_name', 'ilike', '%.docx')
          .not('file_name', 'ilike', '%.xls')
          .not('file_name', 'ilike', '%.xlsx')
          .not('file_url', 'ilike', '%.pdf')
          .not('file_url', 'ilike', '%.doc')
          .not('file_url', 'ilike', '%.docx')
          .not('file_url', 'ilike', '%.xls')
          .not('file_url', 'ilike', '%.xlsx');
        break;
      default:
        // Для 'all' не добавляем фильтры
        break;
    }

    const { data, error } = await query
      .order('created_at', { ascending: false }) // Сначала новые
      .range(offset, offset + limit - 1);

    if (error) {
      logger.error('Error loading filtered messages', error, { component: 'RealtimeChatService', chatId, filter });
      throw error;
    }

    logger.debug('Loaded filtered messages', { count: data?.length || 0, chatId, filter, component: 'RealtimeChatService' });
    
    // Используем ту же трансформацию что и в getChatMessages
    const senderIds = [...new Set(data?.map(msg => msg.sender_id).filter(Boolean) || [])];
    const replyToSenderIds = [...new Set(data?.map(msg => msg.reply_to?.sender_id).filter(Boolean) || [])];
    const allSenderIds = [...new Set([...senderIds, ...replyToSenderIds])];
    
    let profiles: Record<string, any> = {};
    let tgUsers: Record<number, any> = {};
    
    // Загружаем профили платформы
    if (allSenderIds.length > 0) {
      const { data: profilesData } = await supabase
        .from('profiles')
        .select('user_id, first_name, last_name, avatar_url, developer, role_label')
        .in('user_id', allSenderIds);
      
      profiles = (profilesData || []).reduce((acc, profile) => {
        acc[profile.user_id] = profile;
        return acc;
      }, {} as Record<string, any>);
    }
    
    // Загружаем роли Telegram пользователей
    const telegramUserIds = [...new Set(data?.map(msg => msg.telegram_user_id).filter(Boolean) || [])];
    if (telegramUserIds.length > 0) {
      const { data: tgUsersData } = await supabase
        .from('tg_users')
        .select('id, role_label')
        .in('id', telegramUserIds);
      
      tgUsers = (tgUsersData || []).reduce((acc, tgUser) => {
        acc[tgUser.id] = tgUser;
        return acc;
      }, {} as Record<number, any>);
    }
    
    // Преобразуем сообщения с загруженными профилями и ролями
    const transformedMessages: Message[] = (data || []).map(msg => {
      // Определяем роль пользователя
      let roleLabel = 'Нет роли';
      if (profiles[msg.sender_id]?.role_label) {
        roleLabel = profiles[msg.sender_id].role_label;
      } else if (msg.telegram_user_id && tgUsers[msg.telegram_user_id]?.role_label) {
        roleLabel = tgUsers[msg.telegram_user_id].role_label;
      }
      
      // Add backward compatibility mapping for old message types
      let messageType = msg.message_type;
      if (messageType === 'photo') messageType = 'image';
      else if (messageType === 'document') messageType = 'file';
      
      return {
        id: msg.id,
        chat_id: msg.chat_id,
        sender_id: msg.sender_id,
        content: msg.content,
        message_type: messageType as Message['message_type'],
        file_url: msg.file_url,
        file_name: msg.file_name,
        file_type: msg.file_type,
        file_size: msg.file_size,
        voice_duration: msg.voice_duration,
        reply_to_id: msg.reply_to_id,
        interactive_data: (msg as any).interactive_data,
        created_at: msg.created_at,
        updated_at: msg.updated_at,
        is_edited: msg.is_edited,
        is_deleted: msg.is_deleted,
        metadata: {
          ...(msg.metadata as Record<string, any>) || {},
          role_label: roleLabel
        },
        sender_profile: profiles[msg.sender_id] || null,
        // Telegram fields
        telegram_message_id: msg.telegram_message_id,
        telegram_user_id: msg.telegram_user_id,
        telegram_user_data: msg.telegram_user_data as any,
        telegram_topic_id: msg.telegram_topic_id,
        telegram_forward_data: msg.telegram_forward_data as any,
        sync_direction: msg.sync_direction as any,
        reply_to: (msg.reply_to && !Array.isArray(msg.reply_to) && Object.keys(msg.reply_to).length > 0) ? {
          id: msg.reply_to.id,
          chat_id: chatId,
          sender_id: msg.reply_to.sender_id,
          content: msg.reply_to.content,
          message_type: msg.reply_to.message_type as Message['message_type'],
          file_url: null,
          file_name: null,
          file_type: null,
          file_size: null,
          voice_duration: null,
          reply_to_id: null,
          interactive_data: (msg.reply_to as any).interactive_data,
          created_at: msg.reply_to.created_at,
          updated_at: msg.reply_to.created_at,
          is_edited: false,
          is_deleted: false,
          metadata: {},
          sender_profile: profiles[msg.reply_to.sender_id] || null,
          reply_to: null,
          read_by: []
        } : null,
        read_by: []
      };
    });

    return transformedMessages;
  }

  // Отправка текстового сообщения с интеграцией Telegram
  async sendTextMessage(chatId: string, senderId: string, content: string, replyToId?: string): Promise<Message> {
    logger.debug('Sending text message', { chatId, senderId, contentLength: content.length, replyToId, component: 'RealtimeChatService' });
    
    // Проверяем, является ли чат Telegram-синхронизированным
    const { data: chatInfo } = await supabase
      .from('chats')
      .select('telegram_sync, telegram_supergroup_id, telegram_topic_id')
      .eq('id', chatId)
      .single();

    // Если чат синхронизирован с Telegram, отправляем через Edge Function
    if (chatInfo?.telegram_sync && chatInfo?.telegram_supergroup_id) {
      logger.info('Sending message to Telegram-synced chat', { 
        chatId,
        telegramSupergroupId: chatInfo.telegram_supergroup_id,
        component: 'RealtimeChatService'
      });

      // Получаем telegram_message_id для ответа, если есть reply_to_id
      let replyToTelegramMessageId: number | undefined;
      if (replyToId) {
        const { data: replyMessage } = await supabase
          .from('messages')
          .select('telegram_message_id')
          .eq('id', replyToId)
          .single();
        
        replyToTelegramMessageId = replyMessage?.telegram_message_id;
      }

      // Отправляем в Telegram через TelegramChatService
      const telegramResult = await TelegramChatService.sendMessageToTelegram(
        chatId,
        content,
        senderId,
        {
          messageType: 'text',
          replyToTelegramMessageId,
        }
      );

      if (telegramResult.success) {
        // Сообщение сохранено через telegram-send функцию, возвращаем информацию
        let savedMessage = null;
        
        if (telegramResult.messageId) {
          const { data } = await supabase
            .from('messages')
            .select(`
              *,
              reply_to:messages!reply_to_id(
                id,
                content,
                message_type,
                created_at
              )
            `)
            .eq('id', telegramResult.messageId)
            .single();
          savedMessage = data;
        }
        
        // Фолбэк: если по messageId не нашли, ищем последнее сообщение от отправителя
        if (!savedMessage) {
          logger.warn('Message not found by messageId, searching by fallback', { 
            messageId: telegramResult.messageId,
            chatId,
            senderId,
            component: 'RealtimeChatService'
          });
          
          const { data } = await supabase
            .from('messages')
            .select(`
              *,
              reply_to:messages!reply_to_id(
                id,
                content,
                message_type,
                created_at
              )
            `)
            .eq('chat_id', chatId)
            .eq('sender_id', senderId)
            .eq('content', content)
            .eq('message_type', 'text')
            .gte('created_at', new Date(Date.now() - 30000).toISOString()) // Последние 30 секунд
            .order('created_at', { ascending: false })
            .limit(1)
            .single();
          savedMessage = data;
        }

        if (savedMessage) {
          await this.updateChatTimestamp(chatId);
          return await this.transformMessage(savedMessage);
        } else {
          logger.error('Failed to find sent Telegram message in database', { 
            messageId: telegramResult.messageId,
            chatId,
            senderId,
            component: 'RealtimeChatService'
          });
          // Продолжаем с обычной отправкой как фолбэк
        }
      } else {
        logger.error('Failed to send message to Telegram', telegramResult.error, { 
          chatId,
          component: 'RealtimeChatService'
        });
        // Продолжаем с обычной отправкой
      }
    }

    // Обычная отправка сообщения (для не-Telegram чатов или если Telegram не удался)
    const { data, error } = await supabase
      .from('messages')
      .insert({
        chat_id: chatId,
        sender_id: senderId,
        content,
        message_type: 'text',
        reply_to_id: replyToId || null
      })
      .select(`
        *,
        reply_to:messages!reply_to_id(
          id,
          content,
          message_type,
          created_at
        )
      `)
      .single();

    if (error) {
      logger.error('Error sending message', error, { component: 'RealtimeChatService', chatId, senderId });
      throw error;
    }
    
    logger.debug('Message sent successfully', { messageId: data.id, chatId, component: 'RealtimeChatService' });
    
    // Обновляем время последнего обновления чата
    await this.updateChatTimestamp(chatId);
    
    return await this.transformMessage(data);
  }

  // Отправка файла
  async sendFileMessage(chatId: string, senderId: string, file: File, replyToId?: string): Promise<Message> {
    logger.debug('Sending file message', { chatId, senderId, fileName: file.name, fileSize: file.size, component: 'RealtimeChatService' });
    
    // Determine message type based on file MIME type
    let messageType: 'image' | 'file' | 'voice' = 'file';
    if (file.type.startsWith('image/')) {
      messageType = 'image';
    } else if (file.type.startsWith('audio/')) {
      messageType = 'voice';
    }

    // Получаем размеры изображения для сохранения в метаданных
    let imageDimensions = null;
    if (messageType === 'image') {
      try {
        const imageUtils = await import('@/utils/imageUtils');
        imageDimensions = await imageUtils.getImageDimensions(file);
        logger.debug('Image dimensions obtained', { 
          dimensions: imageDimensions, 
          fileName: file.name,
          component: 'RealtimeChatService' 
        });
      } catch (error) {
        logger.warn('Failed to get image dimensions', { 
          error,
          fileName: file.name,
          component: 'RealtimeChatService' 
        });
      }
    }
    
    // Загружаем файл в storage
    const filePath = `${chatId}/${Date.now()}_${file.name}`;
    
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('chat-files')
      .upload(filePath, file, {
        contentType: file.type,
        cacheControl: '3600'
      });

    if (uploadError) throw uploadError;

    // Получаем URL файла 
    const { data: urlData } = supabase.storage
      .from('chat-files')
      .getPublicUrl(filePath);

    // Проверяем, является ли чат Telegram-синхронизированным
    const { data: chatInfo } = await supabase
      .from('chats')
      .select('telegram_sync, telegram_supergroup_id, telegram_topic_id')
      .eq('id', chatId)
      .single();

    let savedMessage = null;

    // Если чат синхронизирован с Telegram, отправляем через Edge Function
    if (chatInfo?.telegram_sync && chatInfo?.telegram_supergroup_id) {
      logger.info('Sending file to Telegram-synced chat', { 
        chatId,
        messageType,
        telegramSupergroupId: chatInfo.telegram_supergroup_id,
        component: 'RealtimeChatService'
      });

      // Получаем telegram_message_id для ответа, если есть reply_to_id
      let replyToTelegramMessageId: number | undefined;
      if (replyToId) {
        const { data: replyMessage } = await supabase
          .from('messages')
          .select('telegram_message_id')
          .eq('id', replyToId)
          .single();
        
        replyToTelegramMessageId = replyMessage?.telegram_message_id;
      }

      // Map message types for Telegram API
      const telegramMessageType = messageType === 'image' ? 'photo' : 'document';

      // Отправляем в Telegram через TelegramChatService
      const telegramResult = await TelegramChatService.sendMessageToTelegram(
        chatId,
        file.name,
        senderId,
        {
          messageType: telegramMessageType,
          fileUrl: urlData.publicUrl,
          fileName: file.name,
          fileType: file.type,
          replyToTelegramMessageId,
        }
      );

      if (telegramResult.success && telegramResult.messageId) {
        // Message was saved through telegram-send function
        const { data } = await supabase
          .from('messages')
          .select(`
            *,
            reply_to:messages!reply_to_id(
              id,
              content,
              message_type,
              created_at
            )
          `)
          .eq('id', telegramResult.messageId)
          .single();
        
        if (data) {
          savedMessage = data;
        }
      }
    }

    // If not Telegram-synced or Telegram send failed, save locally
    if (!savedMessage) {
      const messageData: any = {
        chat_id: chatId,
        sender_id: senderId,
        content: file.name,
        message_type: messageType,
        file_url: urlData.publicUrl,
        file_name: file.name,
        file_type: file.type,
        file_size: file.size,
        reply_to_id: replyToId || null
      };

      // Добавляем размеры изображения в метаданные
      if (imageDimensions) {
        messageData.metadata = {
          imageDimensions: {
            width: imageDimensions.width,
            height: imageDimensions.height,
            aspectRatio: imageDimensions.aspectRatio
          }
        };
      }

      const { data, error } = await supabase
        .from('messages')
        .insert(messageData)
        .select(`
          *,
          reply_to:messages!reply_to_id(
            id,
            content,
            message_type,
            created_at
          )
        `)
        .single();

      if (error) throw error;
      savedMessage = data;
    }

    await this.updateChatTimestamp(chatId);
    return await this.transformMessage(savedMessage);
  }

  // Отправка голосового сообщения
  async sendVoiceMessage(chatId: string, senderId: string, audioBlob: Blob, duration: number, replyToId?: string): Promise<Message> {
    logger.debug('Sending voice message', { chatId, senderId, duration, blobSize: audioBlob.size, component: 'RealtimeChatService' });
    
    // Загружаем аудио в storage
    const fileName = `voice_${Date.now()}.webm`;
    const filePath = `${chatId}/${fileName}`;

    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('chat-files')
      .upload(filePath, audioBlob, {
        contentType: 'audio/webm',
        cacheControl: '3600'
      });

    if (uploadError) throw uploadError;

    // Получаем URL файла
    const { data: urlData } = supabase.storage
      .from('chat-files')
      .getPublicUrl(filePath);

    // Проверяем, является ли чат Telegram-синхронизированным
    const { data: chatInfo } = await supabase
      .from('chats')
      .select('telegram_sync, telegram_supergroup_id, telegram_topic_id')
      .eq('id', chatId)
      .single();

    let savedMessage = null;

    // Если чат синхронизирован с Telegram, отправляем через Edge Function
    if (chatInfo?.telegram_sync && chatInfo?.telegram_supergroup_id) {
      logger.info('Sending voice to Telegram-synced chat', { 
        chatId,
        telegramSupergroupId: chatInfo.telegram_supergroup_id,
        component: 'RealtimeChatService'
      });

      // Получаем telegram_message_id для ответа, если есть reply_to_id
      let replyToTelegramMessageId: number | undefined;
      if (replyToId) {
        const { data: replyMessage } = await supabase
          .from('messages')
          .select('telegram_message_id')
          .eq('id', replyToId)
          .single();
        
        replyToTelegramMessageId = replyMessage?.telegram_message_id;
      }

      // Отправляем в Telegram через TelegramChatService как voice
      const telegramResult = await TelegramChatService.sendMessageToTelegram(
        chatId,
        'Голосовое сообщение',
        senderId,
        {
          messageType: 'voice',
          fileUrl: urlData.publicUrl,
          fileName: fileName,
          fileType: 'audio/webm',
          replyToTelegramMessageId,
        }
      );

      if (telegramResult.success && telegramResult.messageId) {
        // Message was saved through telegram-send function
        const { data } = await supabase
          .from('messages')
          .select(`
            *,
            reply_to:messages!reply_to_id(
              id,
              content,
              message_type,
              created_at
            )
          `)
          .eq('id', telegramResult.messageId)
          .single();
        
        if (data) {
          savedMessage = data;
        }
      }
    }

    // If not Telegram-synced or Telegram send failed, save locally
    if (!savedMessage) {
      const { data, error } = await supabase
        .from('messages')
        .insert({
          chat_id: chatId,
          sender_id: senderId,
          content: 'Голосовое сообщение',
          message_type: 'voice',
          file_url: urlData.publicUrl,
          file_name: fileName,
          file_type: 'audio/webm',
          voice_duration: duration,
          reply_to_id: replyToId || null
        })
        .select(`
          *,
          reply_to:messages!reply_to_id(
            id,
            content,
            message_type,
            created_at
          )
        `)
        .single();

      if (error) throw error;
      savedMessage = data;
    }

    await this.updateChatTimestamp(chatId);
    return await this.transformMessage(savedMessage);
  }

  // Отправка интерактивного сообщения
  async sendInteractiveMessage(chatId: string, senderId: string, interactiveData: any, title?: string): Promise<Message> {
    logger.debug('Sending interactive message', { chatId, senderId, title, component: 'RealtimeChatService' });
    
    const { data, error } = await supabase
      .from('messages')
      .insert({
        chat_id: chatId,
        sender_id: senderId,
        content: title || interactiveData.title || 'Интерактивное сообщение',
        message_type: 'interactive',
        interactive_data: interactiveData
      })
      .select(`
        *,
        reply_to:messages!reply_to_id(
          id,
          content,
          message_type,
          created_at
        )
      `)
      .single();

    if (error) {
      logger.error('Error sending interactive message', error, { component: 'RealtimeChatService', chatId, senderId });
      throw error;
    }
    
    logger.debug('Interactive message sent successfully', { messageId: data.id, chatId, component: 'RealtimeChatService' });
    
    await this.updateChatTimestamp(chatId);
    return await this.transformMessage(data);
  }

  // Пометка сообщения как прочитанного
  async markAsRead(messageId: string, userId: string): Promise<void> {
    const { error } = await supabase
      .from('message_reads')
      .upsert({
        message_id: messageId,
        user_id: userId
      }, {
        onConflict: 'message_id,user_id'
      });

    if (error) throw error;
  }

  // Индикатор печати
  async startTyping(chatId: string, userId: string): Promise<void> {
    const { error } = await supabase
      .from('typing_indicators')
      .upsert({
        chat_id: chatId,
        user_id: userId,
        expires_at: new Date(Date.now() + 10000).toISOString() // 10 секунд
      }, {
        onConflict: 'chat_id,user_id'
      });

    if (error) throw error;
  }

  async stopTyping(chatId: string, userId: string): Promise<void> {
    const { error } = await supabase
      .from('typing_indicators')
      .delete()
      .eq('chat_id', chatId)
      .eq('user_id', userId);

    if (error) throw error;
  }

  async getTypingUsers(chatId: string): Promise<TypingIndicator[]> {
    const { data, error } = await supabase
      .from('typing_indicators')
      .select('*')
      .eq('chat_id', chatId)
      .gt('expires_at', new Date().toISOString());

    if (error) throw error;
    return data || [];
  }

  // Подписка на real-time обновления
  subscribeToChat(chatId: string, callbacks: {
    onMessage?: (message: Message) => void;
    onMessageUpdate?: (message: Message) => void;
    onTyping?: (indicator: TypingIndicator) => void;
    onTypingStop?: (indicator: TypingIndicator) => void;
    onReadStatus?: (read: MessageRead) => void;
  }): RealtimeChannel {
    const channel = supabase
      .channel(`chat:${chatId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'messages',
          filter: `chat_id=eq.${chatId}`
        },
        async (payload) => {
          logger.info('Realtime INSERT received', { 
            chatId, 
            messageId: payload.new.id,
            sync_direction: payload.new.sync_direction,
            component: 'RealtimeChatService' 
          });
          
          if (callbacks.onMessage) {
            try {
              const message = await this.transformMessage(payload.new);
              callbacks.onMessage(message);
            } catch (error) {
              logger.error('Error processing new message from realtime', error, { 
                chatId, 
                messageId: payload.new.id,
                component: 'RealtimeChatService' 
              });
            }
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'messages',
          filter: `chat_id=eq.${chatId}`
        },
        async (payload) => {
          logger.info('Realtime UPDATE received', { 
            chatId, 
            messageId: payload.new.id,
            sync_direction: payload.new.sync_direction,
            component: 'RealtimeChatService' 
          });
          
          if (callbacks.onMessageUpdate) {
            try {
              const message = await this.transformMessage(payload.new);
              callbacks.onMessageUpdate(message);
            } catch (error) {
              logger.error('Error processing updated message from realtime', error, { 
                chatId, 
                messageId: payload.new.id,
                component: 'RealtimeChatService' 
              });
            }
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'typing_indicators',
          filter: `chat_id=eq.${chatId}`
        },
        (payload) => {
          if (callbacks.onTyping) {
            callbacks.onTyping(payload.new as TypingIndicator);
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'DELETE',
          schema: 'public',
          table: 'typing_indicators',
          filter: `chat_id=eq.${chatId}`
        },
        (payload) => {
          if (callbacks.onTypingStop) {
            callbacks.onTypingStop(payload.old as TypingIndicator);
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'message_reads'
        },
        (payload) => {
          if (callbacks.onReadStatus) {
            callbacks.onReadStatus(payload.new as MessageRead);
          }
        }
      )
      .subscribe((status) => {
        logger.info('Chat subscription status changed', { chatId, status, component: 'RealtimeChatService' });
        
        // Enhanced connection monitoring
        if (status === 'SUBSCRIBED') {
          logger.info('Chat subscription established successfully', { chatId, component: 'RealtimeChatService' });
        } else if (status === 'CHANNEL_ERROR' || status === 'CLOSED' || status === 'TIMED_OUT') {
          logger.error('Chat subscription failed', { chatId, status, component: 'RealtimeChatService' });
          
          // Enhanced auto-reconnection with exponential backoff
          const reconnectDelay = status === 'TIMED_OUT' ? 1000 : 3000;
          setTimeout(() => {
            const currentChannel = this.subscriptions.get(chatId);
            if (currentChannel === channel) {
              logger.info('Auto-reconnecting chat subscription', { chatId, component: 'RealtimeChatService' });
              // Remove failed channel and create new one
              this.unsubscribeFromChat(chatId);
              this.subscribeToChat(chatId, callbacks);
            }
          }, reconnectDelay);
        }
      });

    this.subscriptions.set(chatId, channel);
    return channel;
  }

  unsubscribeFromChat(chatId: string): void {
    const channel = this.subscriptions.get(chatId);
    if (channel) {
      supabase.removeChannel(channel);
      this.subscriptions.delete(chatId);
    }
  }

  // Вспомогательные методы
  private async updateChatTimestamp(chatId: string): Promise<void> {
    const { error } = await supabase
      .from('chats')
      .update({ updated_at: new Date().toISOString() })
      .eq('id', chatId);

    if (error) {
      logger.error('Error updating chat timestamp', error, { component: 'RealtimeChatService', chatId });
    }
  }

  private transformMessageWithProfile(data: any): Message {
    // Map Telegram message types to UI types
    const mapMessageType = (type: string): string => {
      switch (type) {
        case 'photo': return 'image';
        case 'document': return 'file';
        case 'audio': return 'file';
        case 'video': return 'file';
        case 'sticker': return 'image';
        default: return type; // text, voice, system, interactive stay the same
      }
    };

    return {
      id: data.id,
      chat_id: data.chat_id,
      sender_id: data.sender_id,
      content: data.content,
      message_type: mapMessageType(data.message_type) as Message['message_type'],
      file_url: data.file_url,
      file_name: data.file_name,
      file_type: data.file_type,
      file_size: data.file_size,
      voice_duration: data.voice_duration,
      reply_to_id: data.reply_to_id,
      interactive_data: data.interactive_data,
      created_at: data.created_at,
      updated_at: data.updated_at,
      is_edited: data.is_edited,
      is_deleted: data.is_deleted,
      metadata: (data.metadata as Record<string, any>) || {},
      sender_profile: data.sender_profile,
      // Telegram fields
      telegram_message_id: data.telegram_message_id,
      telegram_user_id: data.telegram_user_id,
      telegram_user_data: data.telegram_user_data as any,
      telegram_topic_id: data.telegram_topic_id,
      telegram_forward_data: data.telegram_forward_data as any,
      sync_direction: data.sync_direction as any,
      reply_to: data.reply_to ? {
        ...data.reply_to,
        sender_profile: data.reply_to.sender_profile
      } : null,
      read_by: data.read_by || []
    };
  }

  private async transformMessage(data: any): Promise<Message> {
    // Загружаем профиль отправителя отдельно
    let sender_profile = null;
    let roleLabel = 'Нет роли';
    
    if (data.sender_id) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('first_name, last_name, avatar_url, developer, role_label')
        .eq('user_id', data.sender_id)
        .single();
      
      sender_profile = profile;
      if (profile?.role_label) {
        roleLabel = profile.role_label;
      }
    }
    
    // Загружаем роль Telegram пользователя, если профиль платформы не найден или роль не установлена
    if (data.telegram_user_id && (!sender_profile?.role_label)) {
      const { data: tgUser } = await supabase
        .from('tg_users')
        .select('role_label')
        .eq('id', data.telegram_user_id)
        .single();
      
      if (tgUser?.role_label) {
        roleLabel = tgUser.role_label;
      }
    }

    // Map Telegram message types to UI types
    const mapMessageType = (type: string): string => {
      switch (type) {
        case 'photo': return 'image';
        case 'document': return 'file';
        case 'audio': return 'file';
        case 'video': return 'file';
        case 'sticker': return 'image';
        default: return type; // text, voice, system, interactive stay the same
      }
    };

    return {
      id: data.id,
      chat_id: data.chat_id,
      sender_id: data.sender_id,
      content: data.content,
      message_type: mapMessageType(data.message_type) as Message['message_type'],
      file_url: data.file_url,
      file_name: data.file_name,
      file_type: data.file_type,
      file_size: data.file_size,
      voice_duration: data.voice_duration,
      reply_to_id: data.reply_to_id,
      interactive_data: data.interactive_data,
      created_at: data.created_at,
      updated_at: data.updated_at,
      is_edited: data.is_edited,
      is_deleted: data.is_deleted,
      metadata: {
        ...(data.metadata as Record<string, any>) || {},
        role_label: roleLabel
      },
      sender_profile,
      // Telegram fields
      telegram_message_id: data.telegram_message_id,
      telegram_user_id: data.telegram_user_id,
      telegram_user_data: data.telegram_user_data as any,
      telegram_topic_id: data.telegram_topic_id,
      telegram_forward_data: data.telegram_forward_data as any,
      sync_direction: data.sync_direction as any,
      reply_to: data.reply_to,
      read_by: data.read_by || []
    };
  }

  private async getMessageById(messageId: string): Promise<Message> {
    const { data, error } = await supabase
      .from('messages')
      .select(`
        *,
        reply_to:messages!reply_to_id(
          id,
          content,
          message_type,
          created_at
        )
      `)
      .eq('id', messageId)
      .single();

    if (error) throw error;

    return await this.transformMessage(data);
  }

  private async transformChatsWithCounts(data: any[], userId: string): Promise<Chat[]> {
    // Получаем уникальные ID участников для загрузки профилей
    const participantIds = [...new Set(
      data.flatMap(chat => 
        (chat.participants || []).map((p: any) => p.user_id)
      ).filter(Boolean)
    )];

    // Загружаем профили участников одним запросом
    let profiles: Record<string, any> = {};
    if (participantIds.length > 0) {
      const { data: profilesData } = await supabase
        .from('profiles')
        .select('user_id, first_name, last_name, avatar_url, developer')
        .in('user_id', participantIds);
      
      profiles = (profilesData || []).reduce((acc, profile) => {
        acc[profile.user_id] = profile;
        return acc;
      }, {} as Record<string, any>);
    }

    const transformedChats = await Promise.all(data.map(async (chat) => {
      // Получаем последнее сообщение
      let lastMessage = null;
      if (chat.last_message && chat.last_message.length > 0) {
        const lastMsg = chat.last_message[0];
        lastMessage = {
          id: lastMsg.id,
          content: lastMsg.content,
          message_type: lastMsg.message_type,
          created_at: lastMsg.created_at,
          sender_id: lastMsg.sender_id
        };
      }

      // Подсчитываем непрочитанные сообщения
      let unreadCount = 0;
      const userParticipant = chat.participants?.find((p: any) => p.user_id === userId);
      
      if (userParticipant?.last_read_at) {
        const { data: unreadMessages } = await supabase
          .from('messages')
          .select('id')
          .eq('chat_id', chat.id)
          .or('is_deleted.is.false,is_deleted.is.null')
          .neq('sender_id', userId) // Не считаем свои сообщения
          .gt('created_at', userParticipant.last_read_at);
        
        unreadCount = unreadMessages?.length || 0;
      } else {
        // Если пользователь никогда не читал - считаем все сообщения кроме своих
        const { data: allMessages } = await supabase
          .from('messages')
          .select('id')
          .eq('chat_id', chat.id)
          .or('is_deleted.is.false,is_deleted.is.null')
          .neq('sender_id', userId);
        
        unreadCount = allMessages?.length || 0;
      }

      return {
        id: chat.id,
        company_id: chat.company_id,
        created_by: chat.created_by,
        created_at: chat.created_at,
        updated_at: chat.updated_at,
        is_active: chat.is_active,
        metadata: (chat.metadata as Record<string, any>) || {},
        name: chat.name,
        type: chat.type as Chat['type'],
        // Telegram fields
        telegram_sync: chat.telegram_sync || false,
        telegram_supergroup_id: chat.telegram_supergroup_id || null,
        telegram_topic_id: chat.telegram_topic_id || null,
        participants: (chat.participants || []).map((p: any) => ({
          id: p.id,
          chat_id: chat.id,
          user_id: p.user_id,
          role: p.role,
          joined_at: p.joined_at,
          last_read_at: p.last_read_at,
          is_active: p.is_active,
          profile: profiles[p.user_id] || null
        })),
        last_message: lastMessage,
        unread_count: unreadCount
      };
    }));
    
    return transformedChats;
  }

  async deleteChat(chatId: string): Promise<void> {
    logger.info('Deleting chat', { chatId, component: 'RealtimeChatService' });
    
    const { error } = await supabase
      .from('chats')
      .update({ is_active: false })
      .eq('id', chatId);

    if (error) {
      logger.error('Error deleting chat', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
    
    logger.info('Chat deleted successfully', { chatId, component: 'RealtimeChatService' });
  }

  async updateChat(chatId: string, name: string, description?: string): Promise<void> {
    logger.info('Updating chat', { chatId, name, component: 'RealtimeChatService' });
    
    const updateData: any = { name };
    if (description !== undefined) {
      updateData.metadata = { description };
    }
    
    const { error } = await supabase
      .from('chats')
      .update(updateData)
      .eq('id', chatId);

    if (error) {
      logger.error('Error updating chat', error, { component: 'RealtimeChatService', chatId });
      throw error;
    }
    
    logger.info('Chat updated successfully', { chatId, name, component: 'RealtimeChatService' });
  }

  // Глобальная подписка на изменения чатов
  subscribeToChatsUpdates(userId: string, companyId: number | null, callbacks: {
    onChatUpdate?: (chat: any) => void;
    onChatCreate?: (chat: any) => void;
    onChatDelete?: (chat: any) => void;
  }, supergroupId?: number | null): RealtimeChannel {
    logger.info('Subscribing to chats updates', { userId, companyId, supergroupId, component: 'RealtimeChatService' });
    
    const channel = supabase
      .channel('chats-global')
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'chats'
        },
        async (payload) => {
          if (callbacks.onChatUpdate) {
            // Проверяем, имеет ли пользователь доступ к этому чату
            const { data: hasAccess } = await supabase
              .from('chat_participants')
              .select('chat_id')
              .eq('chat_id', payload.new.id)
              .eq('user_id', userId)
              .eq('is_active', true)
              .maybeSingle();

            // Для админов также проверяем компанию/супергруппу
            if (hasAccess || this.isUserAdmin(userId)) {
              // Фильтруем по супергруппе или компании
              if (supergroupId !== null && payload.new.telegram_supergroup_id === supergroupId) {
                callbacks.onChatUpdate(payload.new);
              } else if (supergroupId === null) {
                // Фильтруем по компании
                if (companyId === null && payload.new.company_id === null) {
                  callbacks.onChatUpdate(payload.new);
                } else if (companyId !== null && payload.new.company_id === companyId) {
                  callbacks.onChatUpdate(payload.new);
                }
              }
            }
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'chats'
        },
        async (payload) => {
          if (callbacks.onChatCreate) {
            // Проверяем, имеет ли пользователь доступ к этому чату
            const { data: hasAccess } = await supabase
              .from('chat_participants')
              .select('chat_id')
              .eq('chat_id', payload.new.id)
              .eq('user_id', userId)
              .eq('is_active', true)
              .maybeSingle();

            if (hasAccess || this.isUserAdmin(userId)) {
              // Фильтруем по супергруппе или компании
              if (supergroupId !== null && payload.new.telegram_supergroup_id === supergroupId) {
                callbacks.onChatCreate(payload.new);
              } else if (supergroupId === null) {
                // Фильтруем по компании
                if (companyId === null && payload.new.company_id === null) {
                  callbacks.onChatCreate(payload.new);
                } else if (companyId !== null && payload.new.company_id === companyId) {
                  callbacks.onChatCreate(payload.new);
                }
              }
            }
          }
        }
      )
      .subscribe((status) => {
        logger.debug('Chats subscription status changed', { 
          status, 
          userId, 
          component: 'RealtimeChatService' 
        });
        
        // Enhanced reconnection logic with exponential backoff
        if (status === 'CHANNEL_ERROR' || status === 'CLOSED') {
          logger.warn('Chats subscription disconnected, attempting reconnect', { 
            status, 
            userId,
            component: 'RealtimeChatService' 
          });
          
          // Exponential backoff reconnection with cleanup
          const reconnectDelay = status === 'CHANNEL_ERROR' ? 2000 : 1500;
          setTimeout(() => {
            if (this.chatsSubscription === channel) {
              logger.info('Reconnecting chats subscription', { userId, component: 'RealtimeChatService' });
              // Clean up failed subscription
              this.unsubscribeFromChatsUpdates();
              // Recreate subscription
              this.subscribeToChatsUpdates(userId, companyId, callbacks, supergroupId);
            }
          }, reconnectDelay);
        } else if (status === 'SUBSCRIBED') {
          logger.info('Chats subscription established successfully', { userId, component: 'RealtimeChatService' });
        }
      });

    this.chatsSubscription = channel;
    return channel;
  }

  unsubscribeFromChatsUpdates(): void {
    if (this.chatsSubscription) {
      logger.info('Unsubscribing from chats updates', { component: 'RealtimeChatService' });
      supabase.removeChannel(this.chatsSubscription);
      this.chatsSubscription = null;
    }
  }

  private async isUserAdmin(userId: string): Promise<boolean> {
    const { data } = await supabase
      .from('profiles')
      .select('developer')
      .eq('user_id', userId)
      .maybeSingle();
    
    return data?.developer === true;
  }
}

export const realtimeChatService = new RealtimeChatService();