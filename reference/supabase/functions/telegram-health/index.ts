import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

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
  
  console.log(`Health check using token from: ${tokenSource}, length: ${token.length}, starts with: ${token.substring(0, 10)}...`);
  return token;
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const url = new URL(req.url);
    const debug = url.searchParams.get('debug') === '1';
    
    if (debug) {
      // Debug mode - get detailed bot info
      try {
        const botToken = getBotToken();
        const response = await fetch(`https://api.telegram.org/bot${botToken}/getMe`);
        const result = await response.json();
        
        return new Response(JSON.stringify({
          status: 'debug',
          telegram_api_accessible: true,
          telegram_api_ok: result.ok,
          bot_info: result.result || null,
          bot_token_configured: true,
          timestamp: new Date().toISOString(),
          error: result.description || null
        }, null, 2), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      } catch (error) {
        return new Response(JSON.stringify({
          status: 'debug',
          telegram_api_accessible: false,
          telegram_api_ok: false,
          bot_info: null,
          bot_token_configured: false,
          timestamp: new Date().toISOString(),
          error: error instanceof Error ? error.message : 'Unknown error'
        }, null, 2), {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
    } else {
      // Simple health check
      try {
        const botToken = getBotToken();
        const response = await fetch(`https://api.telegram.org/bot${botToken}/getMe`);
        const result = await response.json();
        
        return new Response(JSON.stringify({
          status: 'healthy',
          bot_ok: result.ok,
          timestamp: new Date().toISOString()
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      } catch (error) {
        return new Response(JSON.stringify({
          status: 'unhealthy',
          bot_ok: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          timestamp: new Date().toISOString()
        }), {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
    }
  } catch (error) {
    console.error('Health check error:', error);
    return new Response(JSON.stringify({
      status: 'error',
      error: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});