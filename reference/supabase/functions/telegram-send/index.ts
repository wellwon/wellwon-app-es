import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders } from "../_shared/cors.ts";

// Initialize Supabase client
const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const supabase = createClient(supabaseUrl, supabaseServiceKey);

// Get bot token fresh on each request to avoid cold start issues
function getBotToken(): string {
  // Try the new token first, fallback to original
  let token = Deno.env.get('TELEGRAM_BOT_TOKEN_SEND')?.trim();
  let tokenSource = 'TELEGRAM_BOT_TOKEN_SEND';
  
  if (!token) {
    token = Deno.env.get('TELEGRAM_BOT_TOKEN')?.trim();
    tokenSource = 'TELEGRAM_BOT_TOKEN';
  }
  
  if (!token) {
    console.error('=== TOKEN CONFIGURATION ERROR ===');
    console.error('Neither TELEGRAM_BOT_TOKEN_SEND nor TELEGRAM_BOT_TOKEN are configured');
    console.error('Available env vars:', Object.keys(Deno.env.toObject()).filter(key => key.includes('TELEGRAM')));
    throw new Error('TELEGRAM_BOT_TOKEN not configured');
  }
  
  console.log(`Using token from: ${tokenSource}, length: ${token.length}, starts with: ${token.substring(0, 10)}...`);
  return token;
}

// Request interface
interface SendMessageRequest {
  chatId: string;
  content: string;
  messageType: 'text' | 'photo' | 'document' | 'voice';
  userId?: string;
  hasFile?: boolean;
  fileName?: string;
  fileUrl?: string;
  replyToTelegramMessageId?: number;
  authHeader?: string;
}

// Telegram API response interface
interface TelegramApiResponse {
  ok: boolean;
  result?: any;
  description?: string;
  error_code?: number;
}

// Send text message to Telegram
async function sendTelegramMessage(
  telegramChatId: number,
  text: string,
  options?: {
    topicId?: number;
    replyToMessageId?: number;
    parseMode?: 'HTML' | 'Markdown';
    isForum?: boolean;
    isGeneralTopic?: boolean;
  }
): Promise<TelegramApiResponse> {
  const botToken = getBotToken();
  
  const payload: any = {
    chat_id: telegramChatId,
    text: text,
  };

  // Handle forum topics properly
  if (options?.isForum && options?.topicId) {
    payload.message_thread_id = options.topicId;
    console.log(`Forum message: chat_id=${telegramChatId}, message_thread_id=${options.topicId}`);
  } else if (options?.isForum && options?.isGeneralTopic) {
    console.log(`General topic message: chat_id=${telegramChatId} (no message_thread_id)`);
  }

  if (options?.replyToMessageId) {
    payload.reply_to_message_id = options.replyToMessageId;
  }

  if (options?.parseMode) {
    payload.parse_mode = options.parseMode;
  }

  console.log('=== TELEGRAM API CALL ===');
  console.log('Mode:', options?.isGeneralTopic ? 'GENERAL TOPIC' : options?.topicId ? 'SPECIFIC TOPIC' : 'REGULAR CHAT');
  console.log('Payload:', JSON.stringify(payload, null, 2));
  
  const response = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const result = await response.json();
  console.log('=== TELEGRAM API RESPONSE ===');
  console.log('Status:', response.status);
  console.log('Response:', JSON.stringify(result, null, 2));
  
  // Auto-retry logic for thread not found errors
  if (!result.ok && result.error_code === 400 && result.description?.includes('message thread not found')) {
    console.log('Message thread not found, retrying without message_thread_id (General topic)...');
    
    // Сохраняем информацию об ошибке для потенциального обновления базы данных
    console.log('TOPIC_DELETED_ERROR detected - topic may need to be marked as deleted');
    
    delete payload.message_thread_id;
    delete payload.reply_to_message_id; // Remove reply if going to General
    
    console.log('=== RETRY AS GENERAL TOPIC ===');
    console.log('Retry Payload:', JSON.stringify(payload, null, 2));
    
    const retryResponse = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    
    const retryResult = await retryResponse.json();
    console.log('=== GENERAL TOPIC RETRY RESPONSE ===');
    console.log('Status:', retryResponse.status);
    console.log('Response:', JSON.stringify(retryResult, null, 2));
    
    // Помечаем в результате, что был retry
    retryResult._wellwon_retry_info = {
      original_error: 'message thread not found',
      retried_as_general: true,
      original_thread_id: options?.topicId
    };
    
    return retryResult;
  }
  
  // If HTML parsing failed, retry without parse_mode
  if (!result.ok && result.error_code === 400 && result.description?.includes('parse')) {
    console.log('HTML parsing failed, retrying without parse_mode...');
    delete payload.parse_mode;
    
    const retryResponse = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    
    const retryResult = await retryResponse.json();
    console.log('=== PARSE MODE RETRY RESPONSE ===');
    console.log('Status:', retryResponse.status);
    console.log('Response:', JSON.stringify(retryResult, null, 2));
    
    return retryResult;
  }

  return result;
}

// Send photo to Telegram
async function sendTelegramPhoto(
  telegramChatId: number,
  photoUrl: string,
  caption?: string,
  options?: {
    topicId?: number;
    replyToMessageId?: number;
    isForum?: boolean;
  }
): Promise<TelegramApiResponse> {
  const botToken = getBotToken();
  
  const payload: any = {
    chat_id: telegramChatId,
    photo: photoUrl,
  };

  if (caption) {
    payload.caption = caption;
  }

  // Handle forum topics properly
  if (options?.isForum && options?.topicId) {
    payload.message_thread_id = options.topicId;
    console.log(`Forum photo: chat_id=${telegramChatId}, message_thread_id=${options.topicId}`);
  }

  if (options?.replyToMessageId) {
    payload.reply_to_message_id = options.replyToMessageId;
  }

  console.log('=== TELEGRAM PHOTO API CALL ===');
  console.log('Payload:', JSON.stringify(payload, null, 2));
  
  const response = await fetch(`https://api.telegram.org/bot${botToken}/sendPhoto`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const result = await response.json();
  console.log('=== TELEGRAM PHOTO API RESPONSE ===');
  console.log('Status:', response.status);
  console.log('Response:', JSON.stringify(result, null, 2));
  
  return result;
}

// Send document to Telegram
async function sendTelegramDocument(
  telegramChatId: number,
  documentUrl: string,
  fileName?: string,
  caption?: string,
  options?: {
    topicId?: number;
    replyToMessageId?: number;
    isForum?: boolean;
  }
): Promise<TelegramApiResponse> {
  const botToken = getBotToken();
  
  const payload: any = {
    chat_id: telegramChatId,
    document: documentUrl,
  };

  if (fileName) {
    // For documents, we can specify filename in the URL or through InputFile
    payload.document = documentUrl;
  }

  if (caption) {
    payload.caption = caption;
  }

  // Handle forum topics properly
  if (options?.isForum && options?.topicId) {
    payload.message_thread_id = options.topicId;
    console.log(`Forum document: chat_id=${telegramChatId}, message_thread_id=${options.topicId}`);
  }

  if (options?.replyToMessageId) {
    payload.reply_to_message_id = options.replyToMessageId;
  }

  console.log('=== TELEGRAM DOCUMENT API CALL ===');
  console.log('Payload:', JSON.stringify(payload, null, 2));
  
  const response = await fetch(`https://api.telegram.org/bot${botToken}/sendDocument`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const result = await response.json();
  console.log('=== TELEGRAM DOCUMENT API RESPONSE ===');
  console.log('Status:', response.status);
  console.log('Response:', JSON.stringify(result, null, 2));
  
  return result;
}

// Validate and get chat info from Supabase
async function getChatInfo(chatId: string): Promise<{
  telegramChatId: number;
  topicId?: number;
  isForum?: boolean;
  isGeneralTopic?: boolean;
  supergroupTitle?: string;
  topicVerified?: boolean;
} | null> {
  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL');
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    
    if (!supabaseUrl || !supabaseKey) {
      throw new Error('Supabase configuration missing');
    }

    // Get chat with telegram data
    const chatResponse = await fetch(`${supabaseUrl}/rest/v1/chats?select=*,telegram_supergroup_id,telegram_topic_id,telegram_sync&id=eq.${chatId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${supabaseKey}`,
        'apikey': supabaseKey,
      },
    });

    if (!chatResponse.ok) {
      console.error('Failed to fetch chat info:', chatResponse.status, await chatResponse.text());
      return null;
    }

    const chatData = await chatResponse.json();
    
    if (!chatData || chatData.length === 0) {
      console.error('Chat not found:', chatId);
      return null;
    }

    const chat = chatData[0];
    
    // Get supergroup info if available
    const supergroupResponse = await fetch(
      `${supabaseUrl}/rest/v1/telegram_supergroups?select=*&id=eq.${chat.telegram_supergroup_id}`,
      {
        headers: {
          'Authorization': `Bearer ${supabaseKey}`,
          'apikey': supabaseKey,
        },
      }
    );

    let supergroupTitle = '';
    let isForum = false;
    
    if (supergroupResponse.ok) {
      const supergroupData = await supergroupResponse.json();
      if (supergroupData && supergroupData.length > 0) {
        supergroupTitle = supergroupData[0].title || '';
        isForum = supergroupData[0].is_forum || false;
      }
    }

    // For General topics in forums, don't set topicId (let Telegram handle it)
    const isGeneralTopic = isForum && (chat.telegram_topic_id === 1 || chat.telegram_topic_id === null);
    
    // Проверяем верификацию топика
    const topicVerified = chat.metadata?.topic_verified === true;
    
    // Если топик не верифицирован и это не General, не отправляем message_thread_id
    const shouldUseTopicId = isGeneralTopic ? false : (topicVerified && chat.telegram_topic_id > 1);
    
    const result = {
      telegramChatId: chat.telegram_supergroup_id,
      topicId: shouldUseTopicId ? chat.telegram_topic_id : undefined,
      isForum,
      isGeneralTopic,
      supergroupTitle,
      topicVerified,
    };

    console.log('Chat info retrieved:', JSON.stringify(result, null, 2));
    return result;
    
  } catch (error) {
    console.error('Error getting chat info:', error);
    return null;
  }
}

// Save message to Supabase after successful Telegram send
async function saveMessageToSupabase(
  request: SendMessageRequest,
  chatInfo: any,
  telegramResult: any
): Promise<string | null> {
  try {
    console.log('=== SAVING MESSAGE TO SUPABASE ===');
    
    // Get user ID from JWT token if available
    const authHeader = request.authHeader;
    const userId = extractUserIdFromJWT(authHeader);
    
    if (!userId) {
      console.error('No user ID found - cannot save message');
      return null;
    }
    
    // Determine actual topic ID used
    const actualTopicId = telegramResult.result?.message_thread_id || chatInfo.topicId;
    
    // Use message types directly as they match DB constraints
    const messageType = request.messageType;

    const messageData = {
      chat_id: request.chatId,
      sender_id: userId,
      content: request.content,
      message_type: messageType,
      file_url: request.fileUrl || null,
      file_name: request.fileName || null,
      file_type: request.messageType === 'photo' ? 'image/jpeg' : 
                 request.messageType === 'document' ? 'application/octet-stream' :
                 request.messageType === 'voice' ? 'audio/webm' : null,
      telegram_message_id: telegramResult.result?.message_id,
      telegram_user_id: telegramResult.result?.from?.id,
      telegram_user_data: telegramResult.result?.from,
      telegram_topic_id: actualTopicId,
      sync_direction: 'web_to_telegram',
      metadata: {
        telegram_sent_at: new Date().toISOString(),
        telegram_chat_id: chatInfo.telegramChatId,
        bot_sent: true,
        reply_to_telegram_message_id: request.replyToTelegramMessageId
      }
    };
    
    // Add reply_to_id if we have it
    if (request.replyToTelegramMessageId) {
      // Find the message in our DB that corresponds to the Telegram message ID
      const { data: replyMessage } = await supabase
        .from('messages')
        .select('id')
        .eq('telegram_message_id', request.replyToTelegramMessageId)
        .eq('chat_id', request.chatId)
        .single();
      
      if (replyMessage) {
        messageData.reply_to_id = replyMessage.id;
      }
    }
    
    const { data: savedMessage, error } = await supabase
      .from('messages')
      .insert(messageData)
      .select('id')
      .single();
    
    if (error) {
      console.error('Failed to save message to Supabase:', error);
      return null;
    }
    
    console.log('Message saved to Supabase:', savedMessage.id);
    return savedMessage.id;
    
  } catch (error) {
    console.error('Error saving message to Supabase:', error);
    return null;
  }
}

// Main message sending function
async function sendMessage(request: SendMessageRequest): Promise<{
  success: boolean;
  telegramMessageId?: number;
  supabaseMessageId?: string;
  error?: string;
  errorCode?: number;
}> {
  try {
    console.log('=== TELEGRAM SEND START ===');
    console.log('Request:', JSON.stringify({
      chatId: request.chatId,
      userId: request.userId,
      messageType: request.messageType,
      hasFile: request.hasFile,
      replyToTelegramMessageId: request.replyToTelegramMessageId
    }, null, 2));

    // Get chat information
    const chatInfo = await getChatInfo(request.chatId);
    if (!chatInfo) {
      throw new Error('Chat not found or not configured for Telegram sync');
    }

    console.log('Chat details:', JSON.stringify(chatInfo, null, 2));

    // Validate content
    const content = validateContent(request.content);
    
    // Send to Telegram based on message type
    let telegramResponse: TelegramApiResponse;
    
    const sendOptions = {
      topicId: chatInfo.topicId,
      replyToMessageId: request.replyToTelegramMessageId,
      isForum: chatInfo.isForum,
      isGeneralTopic: chatInfo.isGeneralTopic,
    };

    switch (request.messageType) {
      case 'text':
        telegramResponse = await sendTelegramMessage(
          chatInfo.telegramChatId,
          content,
          { ...sendOptions, parseMode: 'HTML' }
        );
        break;
        
      case 'photo':
        if (!request.fileUrl) {
          throw new Error('Photo URL is required for photo messages');
        }
        telegramResponse = await sendTelegramPhoto(
          chatInfo.telegramChatId,
          request.fileUrl,
          content || undefined,
          sendOptions
        );
        break;
        
      case 'document':
        if (!request.fileUrl) {
          throw new Error('Document URL is required for document messages');
        }
        telegramResponse = await sendTelegramDocument(
          chatInfo.telegramChatId,
          request.fileUrl,
          request.fileName,
          content || undefined,
          sendOptions
        );
        break;
        
      case 'voice':
        // Voice messages are sent as documents since Telegram's sendVoice requires OGG format
        if (!request.fileUrl) {
          throw new Error('Voice URL is required for voice messages');
        }
        telegramResponse = await sendTelegramDocument(
          chatInfo.telegramChatId,
          request.fileUrl,
          request.fileName || 'voice_message.webm',
          content || 'Голосовое сообщение',
          sendOptions
        );
        break;
        
      default:
        throw new Error(`Unsupported message type: ${request.messageType}`);
    }

    if (!telegramResponse.ok) {
      console.error('=== TELEGRAM API ERROR ===');
      console.error('Error code:', telegramResponse.error_code);
      console.error('Description:', telegramResponse.description);
      
      return {
        success: false,
        error: telegramResponse.description || 'Telegram API error',
        errorCode: telegramResponse.error_code,
      };
    }

    console.log('=== TELEGRAM SEND SUCCESS ===');
    console.log('Message ID:', telegramResponse.result?.message_id);
    
    // Save message to Supabase
    const supabaseMessageId = await saveMessageToSupabase(request, chatInfo, telegramResponse);
    
    return {
      success: true,
      telegramMessageId: telegramResponse.result?.message_id,
      supabaseMessageId,
    };
    
  } catch (error) {
    console.error('=== TELEGRAM SEND ERROR ===');
    console.error('Send message error:', error);
    console.error('Error details:', JSON.stringify({
      message: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      request: {
        chatId: request.chatId,
        telegramChatId: chatInfo?.telegramChatId,
        topicId: chatInfo?.topicId,
        isForum: chatInfo?.isForum,
      },
    }, null, 2));
    
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// Validation functions
function validateContent(content: string): string {
  if (!content || content.trim().length === 0) {
    throw new Error('Message content cannot be empty');
  }
  
  // Telegram has a 4096 character limit for text messages
  if (content.length > 4096) {
    return content.substring(0, 4093) + '...';
  }
  
  return content.trim();
}

function validateFileUrl(fileUrl?: string): string | undefined {
  if (!fileUrl) return undefined;
  
  try {
    const url = new URL(fileUrl);
    // Only allow certain domains for security
    const allowedDomains = ['supabase.co', 'githubusercontent.com', 'telegram.org'];
    const isAllowed = allowedDomains.some(domain => url.hostname.includes(domain));
    
    if (!isAllowed) {
      throw new Error(`File URL domain not allowed: ${url.hostname}`);
    }
    
    return fileUrl;
  } catch (error) {
    throw new Error(`Invalid file URL: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// Extract user ID from JWT token
function extractUserIdFromJWT(authHeader: string | null): string | null {
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  
  try {
    const token = authHeader.substring(7);
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub || null;
  } catch (error) {
    console.error('Failed to extract user ID from JWT:', error);
    return null;
  }
}

// HTTP Server
serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    if (req.method !== 'POST') {
      return new Response('Method not allowed', { 
        status: 405,
        headers: corsHeaders 
      });
    }

    // Parse request
    const body = await req.json();
    const authHeader = req.headers.get('Authorization');
    const userId = extractUserIdFromJWT(authHeader);

    // Validate required fields
    if (!body.chatId || !body.content || !body.messageType) {
      return new Response(JSON.stringify({
        error: 'Missing required fields: chatId, content, messageType'
      }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Validate file URL if provided
    let validatedFileUrl: string | undefined;
    try {
      validatedFileUrl = validateFileUrl(body.fileUrl);
    } catch (error) {
      return new Response(JSON.stringify({
        error: error instanceof Error ? error.message : 'Invalid file URL'
      }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Prepare request
    const sendRequest: SendMessageRequest = {
      chatId: body.chatId,
      content: body.content,
      messageType: body.messageType,
      userId: userId || undefined,
      hasFile: !!body.fileUrl,
      fileName: body.fileName,
      fileUrl: validatedFileUrl,
      replyToTelegramMessageId: body.replyToTelegramMessageId,
      authHeader: authHeader || undefined,
    };

    // Send message
    const result = await sendMessage(sendRequest);

    if (result.success) {
      return new Response(JSON.stringify({
        success: true,
        telegramMessageId: result.telegramMessageId,
        supabaseMessageId: result.supabaseMessageId,
        message: 'Message sent successfully'
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    } else {
      // Map Telegram error codes to HTTP status codes
      let httpStatus = 500;
      if (result.errorCode === 400) httpStatus = 400;
      if (result.errorCode === 403) httpStatus = 403;
      if (result.errorCode === 404) httpStatus = 404;
      if (result.errorCode === 429) httpStatus = 429;
      
      return new Response(JSON.stringify({
        success: false,
        error: result.error,
        errorCode: result.errorCode
      }), {
        status: httpStatus,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

  } catch (error) {
    console.error('Request processing error:', error);
    return new Response(JSON.stringify({
      success: false,
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});