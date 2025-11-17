
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

// Function to get bot token with fallback
function getBotToken(): string | null {
  return Deno.env.get('TELEGRAM_BOT_TOKEN') || Deno.env.get('TELEGRAM_BOT_TOKEN_SEND') || null;
}

serve(async (req) => {
  console.log(`${req.method} ${req.url}`);

  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const url = new URL(req.url);
    const fileId = url.searchParams.get('file_id');
    const filePath = url.searchParams.get('file_path');

    if (!fileId && !filePath) {
      return new Response('Missing file_id or file_path parameter', { 
        status: 400,
        headers: corsHeaders 
      });
    }

    const telegramBotToken = getBotToken();
    if (!telegramBotToken) {
      return new Response('Telegram bot token not configured', { 
        status: 500,
        headers: corsHeaders 
      });
    }

    let telegramFilePath = filePath;

    // If we only have file_id, get the file_path from Telegram
    if (!telegramFilePath && fileId) {
      const fileResponse = await fetch(`https://api.telegram.org/bot${telegramBotToken}/getFile?file_id=${fileId}`);
      const fileData = await fileResponse.json();
      
      if (!fileData.ok) {
        console.error('Failed to get file info from Telegram:', fileData);
        return new Response('Failed to get file info from Telegram', { 
          status: 404,
          headers: corsHeaders 
        });
      }

      telegramFilePath = fileData.result.file_path;
    }

    // Download file from Telegram
    const downloadResponse = await fetch(`https://api.telegram.org/file/bot${telegramBotToken}/${telegramFilePath}`);
    
    if (!downloadResponse.ok) {
      console.error('Failed to download file from Telegram');
      return new Response('File not found', { 
        status: 404,
        headers: corsHeaders 
      });
    }

    // Determine content type based on file extension
    const extension = telegramFilePath?.split('.').pop()?.toLowerCase();
    let contentType = 'application/octet-stream';
    let contentDisposition = 'inline';
    
    switch (extension) {
      case 'jpg':
      case 'jpeg':
        contentType = 'image/jpeg';
        break;
      case 'png':
        contentType = 'image/png';
        break;
      case 'gif':
        contentType = 'image/gif';
        break;
      case 'webp':
        contentType = 'image/webp';
        break;
      case 'mp4':
        contentType = 'video/mp4';
        break;
      case 'mp3':
        contentType = 'audio/mpeg';
        break;
      case 'ogg':
      case 'oga':
      case 'opus':
        contentType = 'audio/ogg';
        break;
      case 'm4a':
        contentType = 'audio/mp4';
        break;
      case 'amr':
        contentType = 'audio/amr';
        break;
      case 'aac':
        contentType = 'audio/aac';
        break;
      case 'pdf':
        contentType = 'application/pdf';
        contentDisposition = 'attachment';
        break;
      case 'doc':
        contentType = 'application/msword';
        contentDisposition = 'attachment';
        break;
      case 'docx':
        contentType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
        contentDisposition = 'attachment';
        break;
      case 'xls':
        contentType = 'application/vnd.ms-excel';
        contentDisposition = 'attachment';
        break;
      case 'xlsx':
        contentType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
        contentDisposition = 'attachment';
        break;
      case 'zip':
        contentType = 'application/zip';
        contentDisposition = 'attachment';
        break;
      case 'rar':
        contentType = 'application/vnd.rar';
        contentDisposition = 'attachment';
        break;
      case '7z':
        contentType = 'application/x-7z-compressed';
        contentDisposition = 'attachment';
        break;
      case 'txt':
        contentType = 'text/plain';
        contentDisposition = 'attachment';
        break;
      case 'csv':
        contentType = 'text/csv';
        contentDisposition = 'attachment';
        break;
      case 'xml':
        contentType = 'application/xml';
        contentDisposition = 'attachment';
        break;
      case 'json':
        contentType = 'application/json';
        contentDisposition = 'attachment';
        break;
    }

    // Stream the file back to client
    const fileBlob = await downloadResponse.blob();
    
    return new Response(fileBlob, {
      headers: {
        ...corsHeaders,
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
        'Content-Disposition': contentDisposition
      }
    });

  } catch (error) {
    console.error('Proxy error:', error);
    
    return new Response(JSON.stringify({ 
      error: 'Internal server error', 
      details: error instanceof Error ? error.message : 'Unknown error'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
});
