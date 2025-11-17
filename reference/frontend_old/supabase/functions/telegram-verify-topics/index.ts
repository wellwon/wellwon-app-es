import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const supabase = createClient(supabaseUrl, supabaseServiceKey);

function getBotToken(): string {
  let token = Deno.env.get('TELEGRAM_BOT_TOKEN_SEND')?.trim();
  if (!token) {
    token = Deno.env.get('TELEGRAM_BOT_TOKEN')?.trim();
  }
  if (!token) {
    throw new Error('TELEGRAM_BOT_TOKEN not configured');
  }
  return token;
}

// Проверяем существование топика в Telegram (используем reopenForumTopic для надежной проверки)
async function verifyTopicExists(chatId: number, topicId: number): Promise<{ exists: boolean; status: 'verified' | 'deleted' | 'unknown' }> {
  const botToken = getBotToken();
  
  try {
    // Для General топика (topicId === 1) используем reopenGeneralForumTopic
    const apiMethod = topicId === 1 ? 'reopenGeneralForumTopic' : 'reopenForumTopic';
    const requestBody = topicId === 1 
      ? { chat_id: chatId }
      : { chat_id: chatId, message_thread_id: topicId };

    console.log(`Checking topic ${topicId} using ${apiMethod}`);
    
    const response = await fetch(`https://api.telegram.org/bot${botToken}/${apiMethod}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    const result = await response.json();
    
    if (result.ok) {
      // Топик был закрыт и мы его открыли - нужно закрыть обратно
      console.log(`Topic ${topicId} was closed, reopened successfully - closing back`);
      
      const closeMethod = topicId === 1 ? 'closeGeneralForumTopic' : 'closeForumTopic';
      const closeBody = topicId === 1 
        ? { chat_id: chatId }
        : { chat_id: chatId, message_thread_id: topicId };
        
      await fetch(`https://api.telegram.org/bot${botToken}/${closeMethod}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(closeBody),
      });
      
      return { exists: true, status: 'verified' };
    } else if (result.error_code === 400) {
      if (result.description?.includes('message thread not found') || 
          result.description?.includes('forum topic not found')) {
        // Топик не существует
        console.log(`Topic ${topicId} not found: ${result.description}`);
        return { exists: false, status: 'deleted' };
      } else if (result.description?.includes('topic is not closed') || 
                 result.description?.includes('TOPIC_NOT_MODIFIED')) {
        // Топик уже открыт - значит существует
        console.log(`Topic ${topicId} is already open: ${result.description}`);
        return { exists: true, status: 'verified' };
      } else if (result.description?.includes('TOPIC_ID_INVALID')) {
        // Топик с невалидным ID - считаем удаленным
        console.log(`Topic ${topicId} has invalid ID: ${result.description}`);
        return { exists: false, status: 'deleted' };
      } else {
        // Другая 400 ошибка - неизвестное состояние
        console.log(`Unknown 400 error for topic ${topicId}: ${result.description}`);
        return { exists: false, status: 'unknown' };
      }
    } else {
      // Другие ошибки (403 нет прав, 429 rate limit и т.д.) - неизвестное состояние
      console.log(`Cannot verify topic ${topicId} (${result.error_code}): ${result.description}`);
      return { exists: false, status: 'unknown' };
    }
  } catch (error) {
    console.error(`Error verifying topic ${topicId}:`, error);
    return { exists: false, status: 'unknown' };
  }
}

// Перемещает сообщения из удаленного топика в General
async function moveMessagesToGeneral(deletedChatId: string, generalChatId: string): Promise<number> {
  const { data: messages, error } = await supabase
    .from('messages')
    .select('id, metadata')
    .eq('chat_id', deletedChatId);

  if (error) {
    console.error('Error fetching messages:', error);
    return 0;
  }

  if (!messages || messages.length === 0) {
    return 0;
  }

  // Обновляем все сообщения
  const updatedMessages = messages.map(msg => ({
    id: msg.id,
    chat_id: generalChatId,
    metadata: {
      ...msg.metadata,
      moved_from_deleted_topic: true,
      moved_at: new Date().toISOString(),
      original_chat_id: deletedChatId
    }
  }));

  const { error: updateError } = await supabase
    .from('messages')
    .upsert(updatedMessages);

  if (updateError) {
    console.error('Error moving messages:', updateError);
    return 0;
  }

  console.log(`Moved ${messages.length} messages from deleted topic to General`);
  return messages.length;
}

// Объединяет дублированные General чаты
async function deduplicateGeneralChats(supergroupId: number, generalChats: any[]): Promise<{ canonicalChat: any; duplicates: any[]; messagesMoved: number }> {
  if (generalChats.length <= 1) {
    return { canonicalChat: generalChats[0] || null, duplicates: [], messagesMoved: 0 };
  }

  console.log(`Found ${generalChats.length} General chats to deduplicate`);
  
  // Выбираем канонический чат: приоритет topic_id=1, затем самый ранний created_at
  const canonicalChat = generalChats.reduce((best, current) => {
    // Приоритет topic_id=1
    if (current.telegram_topic_id === 1 && best.telegram_topic_id !== 1) return current;
    if (best.telegram_topic_id === 1 && current.telegram_topic_id !== 1) return best;
    
    // Если оба topic_id=1 или оба null/другие, выбираем более ранний
    return new Date(current.created_at) < new Date(best.created_at) ? current : best;
  });

  const duplicates = generalChats.filter(chat => chat.id !== canonicalChat.id);
  console.log(`Canonical General chat: ${canonicalChat.id}, duplicates: ${duplicates.length}`);

  let totalMessagesMoved = 0;

  // Перемещаем сообщения из дубликатов в канонический чат
  for (const duplicate of duplicates) {
    const messagesMoved = await moveMessagesToGeneral(duplicate.id, canonicalChat.id);
    totalMessagesMoved += messagesMoved;

    // Помечаем дубликат как неактивный и объединенный
    const updatedMetadata = {
      ...duplicate.metadata,
      duplicate_general: true,
      merged_into: canonicalChat.id,
      merged_at: new Date().toISOString()
    };
    
    const { error: updateError } = await supabase
      .from('chats')
      .update({
        is_active: false,
        metadata: updatedMetadata
      })
      .eq('id', duplicate.id);
      
    if (updateError) {
      console.error(`Error updating duplicate General chat ${duplicate.id}:`, updateError);
    }
  }

  console.log(`Deduplicated ${duplicates.length} General chats, moved ${totalMessagesMoved} messages`);
  return { canonicalChat, duplicates, messagesMoved: totalMessagesMoved };
}

serve(async (req) => {
  // Handle CORS
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { supergroupId, dryRun = false } = await req.json();

    if (!supergroupId) {
      return new Response(
        JSON.stringify({ error: 'supergroupId is required' }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      );
    }

    console.log(`Verifying topics for supergroup: ${supergroupId}, dryRun: ${dryRun}`);

    // Получаем все чаты для этой супергруппы
    const { data: chats, error: chatsError } = await supabase
      .from('chats')
      .select('id, name, telegram_topic_id, metadata, is_active')
      .eq('telegram_supergroup_id', supergroupId)
      .eq('is_active', true);

    if (chatsError) {
      throw chatsError;
    }

    if (!chats || chats.length === 0) {
      console.log(`No active chats found for supergroup ${supergroupId}`);
      return new Response(
        JSON.stringify({ message: 'No chats found for this supergroup' }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    console.log(`Found ${chats.length} chats to verify:`, chats.map(c => ({ id: c.id, name: c.name, topicId: c.telegram_topic_id })));

    const results = [];
    let generalChat = null;
    const deletedTopics = [];
    let generalDeduplicationResult = { canonicalChat: null, duplicates: [], messagesMoved: 0 };

    // Находим все General чаты для дедупликации
    const generalChats = chats.filter(chat => chat.telegram_topic_id === 1 || chat.telegram_topic_id === null);
    
    if (!dryRun && generalChats.length > 1) {
      // Объединяем дублированные General чаты
      generalDeduplicationResult = await deduplicateGeneralChats(supergroupId, generalChats);
      generalChat = generalDeduplicationResult.canonicalChat;
    } else {
      generalChat = generalChats[0] || null;
    }

    // Проверяем каждый топик
    for (const chat of chats) {
      const topicId = chat.telegram_topic_id;
      
      if (topicId === 1 || topicId === null) {
        // General топик всегда считается существующим
        results.push({
          chatId: chat.id,
          topicId: topicId,
          name: chat.name,
          exists: true,
          status: 'verified' as const,
          isGeneral: true
        });
        continue;
      }

      console.log(`Verifying topic ${topicId} for chat ${chat.id}`);
      const verificationResult = await verifyTopicExists(supergroupId, topicId);
      
      results.push({
        chatId: chat.id,
        topicId: topicId,
        name: chat.name,
        exists: verificationResult.exists,
        status: verificationResult.status,
        isGeneral: false
      });

      if (!verificationResult.exists && verificationResult.status === 'deleted') {
        deletedTopics.push(chat);
      }
    }

    // Если не dry run, обновляем данные
    let totalMovedMessages = 0;
    
    if (!dryRun) {
      // Помечаем существующие топики как проверенные и активные
      const existingTopics = results.filter(r => r.exists);
      if (existingTopics.length > 0) {
        console.log(`Updating ${existingTopics.length} existing topics as verified`);
        
        // Получаем ID дубликатов General чатов, чтобы не активировать их
        const duplicateGeneralIds = generalDeduplicationResult.duplicates.map(d => d.id);
        
        for (const topic of existingTopics) {
          const chat = chats.find(c => c.id === topic.chatId);
          if (chat) {
            // Пропускаем дубликаты General чатов - они должны остаться неактивными
            if (duplicateGeneralIds.includes(chat.id)) {
              console.log(`Skipping duplicate General chat ${chat.id} - keeping it inactive`);
              continue;
            }

            const updatedMetadata = {
              ...chat.metadata,
              topic_verified: true,
              verified_at: new Date().toISOString()
            };
            
            const { error: updateError } = await supabase
              .from('chats')
              .update({
                is_active: true,
                metadata: updatedMetadata
              })
              .eq('id', chat.id);
              
            if (updateError) {
              console.error(`Error updating chat ${chat.id}:`, updateError);
            }
          }
        }
      }

      // Обрабатываем удаленные топики
      if (deletedTopics.length > 0 && generalChat) {
        console.log(`Processing ${deletedTopics.length} deleted topics`);
        
        for (const deletedChat of deletedTopics) {
          // Перемещаем сообщения в General
          const movedCount = await moveMessagesToGeneral(deletedChat.id, generalChat.id);
          totalMovedMessages += movedCount;

          // Помечаем чат как неактивный и удаленный
          const updatedMetadata = {
            ...deletedChat.metadata,
            topic_deleted: true,
            verified_deleted_at: new Date().toISOString(),
            moved_messages_to: generalChat.id
          };
          
          const { error: updateError } = await supabase
            .from('chats')
            .update({
              is_active: false,
              metadata: updatedMetadata
            })
            .eq('id', deletedChat.id);
            
          if (updateError) {
            console.error(`Error updating deleted chat ${deletedChat.id}:`, updateError);
          }
        }
      }

      console.log(`Processed ${deletedTopics.length} deleted topics, moved ${totalMovedMessages} messages`);
    }

    return new Response(
      JSON.stringify({
        supergroupId,
        totalChats: chats.length,
        verificationResults: results,
        deletedTopicsCount: deletedTopics.length,
        processedChanges: !dryRun,
        duplicatesMerged: generalDeduplicationResult.duplicates.length > 0 ? {
          count: generalDeduplicationResult.duplicates.length,
          canonicalChatId: generalDeduplicationResult.canonicalChat?.id,
          duplicateIds: generalDeduplicationResult.duplicates.map(d => d.id),
          messagesMoved: generalDeduplicationResult.messagesMoved
        } : null,
        summary: {
          existingTopics: results.filter(r => r.exists && r.status === 'verified').length,
          deletedTopics: results.filter(r => !r.exists && r.status === 'deleted').length,
          unknownTopics: results.filter(r => r.status === 'unknown').length,
          general: results.filter(r => r.isGeneral).length,
          messagesMoved: totalMovedMessages + generalDeduplicationResult.messagesMoved,
          generalDuplicatesMerged: generalDeduplicationResult.duplicates.length
        }
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    );

  } catch (error) {
    console.error('Error in topic verification:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    );
  }
});