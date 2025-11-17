import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders } from "../_shared/cors.ts";

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

// Function to get bot token with fallback
function getBotToken(): string | null {
  return Deno.env.get('TELEGRAM_BOT_TOKEN') || Deno.env.get('TELEGRAM_BOT_TOKEN_SEND') || null;
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

// Download file from Telegram and upload to Supabase Storage
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
    return { url: null, status: 'proxy' };
  }

  try {
    // Get file path from Telegram
    const fileResponse = await fetch(`https://api.telegram.org/bot${telegramBotToken}/getFile?file_id=${fileId}`);
    const fileData = await fileResponse.json();
    
    if (!fileData.ok) {
      console.error('Failed to get file info from Telegram:', fileData);
      return { url: null, status: 'proxy' };
    }

    const telegramFilePath = fileData.result.file_path;
    
    // Download file from Telegram
    const downloadResponse = await fetch(`https://api.telegram.org/file/bot${telegramBotToken}/${telegramFilePath}`);
    if (!downloadResponse.ok) {
      console.error('Failed to download file from Telegram');
      return { url: null, status: 'proxy', filePath: telegramFilePath };
    }

    const fileBuffer = await downloadResponse.arrayBuffer();
    
    // Generate organized path
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const safeName = fileName.replace(/[^a-zA-Z0-9._-]/g, '_');
    const topicPath = topicId ? topicId : 'general';
    const storagePath = `tg/${supergroupId}/${topicPath}/${year}/${month}/backfill_${messageId}_${safeName}`;
    
    // Upload to Supabase Storage
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('chat-files')
      .upload(storagePath, fileBuffer, {
        contentType: mimeType || 'application/octet-stream',
        cacheControl: '3600'
      });

    if (uploadError) {
      console.error('Failed to upload file to storage:', uploadError);
      return { url: null, status: 'proxy', filePath: telegramFilePath };
    }

    // Get public URL
    const { data: urlData } = supabase.storage
      .from('chat-files')
      .getPublicUrl(uploadData.path);

    return { url: urlData.publicUrl, status: 'stored', filePath: telegramFilePath };
  } catch (error) {
    console.error('Error downloading and storing file:', error);
    return { url: null, status: 'proxy' };
  }
}

// Normalize message type for database storage
function normalizeMessageType(telegramType: string): string {
  switch (telegramType) {
    case 'photo': return 'image';
    case 'document': return 'file';
    case 'video': return 'video';
    case 'audio': return 'file';
    case 'voice': return 'voice';
    default: return telegramType;
  }
}

// Extract file ID from message metadata
function extractFileId(message: any): { fileId: string | null, originalFileName: string | null, mimeType: string | null } {
  const rawMessage = message.metadata?.raw_message;
  if (!rawMessage) return { fileId: null, originalFileName: null, mimeType: null };

  if (rawMessage.photo && rawMessage.photo.length > 0) {
    const largestPhoto = rawMessage.photo[rawMessage.photo.length - 1];
    return {
      fileId: largestPhoto.file_id,
      originalFileName: `photo_${largestPhoto.file_id}.jpg`,
      mimeType: 'image/jpeg'
    };
  }

  if (rawMessage.document) {
    return {
      fileId: rawMessage.document.file_id,
      originalFileName: rawMessage.document.file_name || `document_${rawMessage.document.file_id}`,
      mimeType: rawMessage.document.mime_type
    };
  }

  if (rawMessage.video) {
    return {
      fileId: rawMessage.video.file_id,
      originalFileName: `video_${rawMessage.video.file_id}.mp4`,
      mimeType: rawMessage.video.mime_type || 'video/mp4'
    };
  }

  if (rawMessage.audio) {
    return {
      fileId: rawMessage.audio.file_id,
      originalFileName: rawMessage.audio.file_name || `audio_${rawMessage.audio.file_id}.mp3`,
      mimeType: rawMessage.audio.mime_type || 'audio/mpeg'
    };
  }

  if (rawMessage.voice) {
    return {
      fileId: rawMessage.voice.file_id,
      originalFileName: `voice_${rawMessage.voice.file_id}.ogg`,
      mimeType: 'audio/ogg'
    };
  }

  return { fileId: null, originalFileName: null, mimeType: null };
}

serve(async (req) => {
  console.log(`${req.method} ${req.url}`);

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

    const { limit = 50, chatId = null, retryProxy = false } = await req.json();

    console.log(`Starting media backfill - limit: ${limit}, chatId: ${chatId}, retryProxy: ${retryProxy}`);

    // Find messages that need backfill
    let query = supabase
      .from('messages')
      .select('*, chats!inner(telegram_supergroup_id, telegram_topic_id)')
      .in('message_type', ['photo', 'document', 'video', 'audio', 'voice'])
      .not('metadata', 'is', null)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (retryProxy) {
      // Retry messages with proxy status to convert them to storage
      query = query.eq('file_status', 'proxy').not('telegram_file_id', 'is', null);
    } else {
      // Original logic: messages without file_url
      query = query.is('file_url', null);
    }

    if (chatId) {
      query = query.eq('chat_id', chatId);
    }

    const { data: messages, error } = await query;

    if (error) {
      console.error('Error fetching messages:', error);
      return new Response(JSON.stringify({ error: 'Failed to fetch messages' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    console.log(`Found ${messages.length} messages to process`);

    let processed = 0;
    let errors = 0;
    const results = [];

    for (const message of messages) {
      try {
        let fileId = message.telegram_file_id;
        let fileName = message.file_name;
        let mimeType = message.file_type;

        // If we don't have telegram_file_id, try to extract from metadata
        if (!fileId) {
          const { fileId: extractedFileId, originalFileName, mimeType: extractedMimeType } = extractFileId(message);
          fileId = extractedFileId;
          fileName = originalFileName || fileName;
          mimeType = extractedMimeType || mimeType;
        }
        
        if (!fileId) {
          console.log(`No file ID found for message ${message.id}`);
          continue;
        }

        console.log(`Processing message ${message.id} with file ID: ${fileId}`);

        // Download and store the file
        const result = await downloadAndStoreFile(
          fileId, 
          fileName || 'unknown_file', 
          mimeType,
          message.chats.telegram_supergroup_id,
          message.chats.telegram_topic_id,
          message.telegram_message_id
        );
        
        if (result.url) {
          // Update message with file URL and status
          const normalizedType = normalizeMessageType(message.message_type);
          
          const updateData: any = {
            file_url: result.url,
            file_status: result.status,
            message_type: normalizedType,
            updated_at: new Date().toISOString()
          };

          // Update telegram fields if we have them
          if (!message.telegram_file_id && fileId) {
            updateData.telegram_file_id = fileId;
          }
          if (!message.telegram_file_path && result.filePath) {
            updateData.telegram_file_path = result.filePath;
          }
          if (!message.file_name && fileName) {
            updateData.file_name = fileName;
          }
          if (!message.file_type && mimeType) {
            updateData.file_type = mimeType;
          }

          const { error: updateError } = await supabase
            .from('messages')
            .update(updateData)
            .eq('id', message.id);

          if (updateError) {
            console.error(`Failed to update message ${message.id}:`, updateError);
            errors++;
          } else {
            console.log(`Successfully processed message ${message.id} with status: ${result.status}`);
            processed++;
            results.push({
              messageId: message.id,
              fileUrl: result.url,
              originalType: message.message_type,
              normalizedType,
              status: result.status
            });
          }
        } else {
          // Generate proxy URL as last resort
          const proxyUrl = `${supabaseUrl}/functions/v1/telegram-file-proxy?file_id=${fileId}`;
          
          const { error: updateError } = await supabase
            .from('messages')
            .update({
              file_url: proxyUrl,
              file_status: 'proxy',
              telegram_file_id: fileId,
              updated_at: new Date().toISOString()
            })
            .eq('id', message.id);

          if (updateError) {
            console.error(`Failed to update message ${message.id} with proxy URL:`, updateError);
            errors++;
          } else {
            console.log(`Set proxy URL for message ${message.id}`);
            processed++;
            results.push({
              messageId: message.id,
              fileUrl: proxyUrl,
              status: 'proxy'
            });
          }
        }
      } catch (error) {
        console.error(`Error processing message ${message.id}:`, error);
        errors++;
      }

      // Add small delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    const response = {
      success: true,
      totalFound: messages.length,
      processed,
      errors,
      results
    };

    console.log('Backfill completed:', response);

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    console.error('Backfill error:', error);
    
    return new Response(JSON.stringify({ 
      error: 'Internal server error', 
      details: error instanceof Error ? error.message : 'Unknown error'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
});
