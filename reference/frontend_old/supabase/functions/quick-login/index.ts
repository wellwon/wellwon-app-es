import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.52.0'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface QuickLoginRequest {
  email: string;
  userType: string;
}

Deno.serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Check if request is from development environment
    const origin = req.headers.get('origin') || req.headers.get('referer') || '';
    const isDevelopment = origin.includes('localhost') || 
                         origin.includes('127.0.0.1') || 
                         origin.includes('lovableproject.com') ||
                         Deno.env.get('ENABLE_QUICK_LOGIN') === 'true';
    
    console.log(`Quick login attempt from origin: ${origin}, isDevelopment: ${isDevelopment}`);
    
    if (!isDevelopment) {
      console.log('Quick login blocked: not in development mode');
      console.log(`Environment check - ENABLE_QUICK_LOGIN: ${Deno.env.get('ENABLE_QUICK_LOGIN')}`);
      return new Response(
        JSON.stringify({ error: 'Quick login only available in development mode' }),
        { 
          status: 403, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    const { email, userType } = await req.json() as QuickLoginRequest;
    
    if (!email || !userType) {
      return new Response(
        JSON.stringify({ error: 'Email and userType are required' }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    // Get the development password from secrets
    const devPassword = Deno.env.get('DEV_TEST_PASSWORD');
    if (!devPassword) {
      console.error('DEV_TEST_PASSWORD secret not configured');
      return new Response(
        JSON.stringify({ error: 'Development password not configured' }),
        { 
          status: 500, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    // Create admin Supabase client
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    );

    // Attempt login with the provided credentials
    const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
      email,
      password: devPassword,
    });

    if (authError) {
      console.error('Authentication failed:', authError);
      return new Response(
        JSON.stringify({ error: 'Authentication failed', details: authError.message }),
        { 
          status: 401, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    if (!authData.user || !authData.session) {
      return new Response(
        JSON.stringify({ error: 'No user or session returned' }),
        { 
          status: 401, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    // Log the successful login for audit purposes
    console.log(`Quick login successful: ${email} as ${userType} at ${new Date().toISOString()}`);

    // Return the session data
    return new Response(
      JSON.stringify({ 
        user: authData.user,
        session: authData.session,
        message: `Successfully logged in as ${userType}: ${email}`
      }),
      { 
        status: 200, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error) {
    console.error('Quick login error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});