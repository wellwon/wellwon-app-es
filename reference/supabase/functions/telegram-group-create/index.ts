import { corsHeaders } from '../_shared/cors.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.52.0';

const TELEGRAM_MANAGE_URL = 'https://telegram-manage.onrender.com';

interface TelegramGroupRequest {
  title: string;
  description: string;
  photo_url: string;
  company_id: number;
}

interface TelegramGroupResponse {
  success: boolean;
  group_id?: number;
  group_title?: string;
  invite_link?: string;
  bots_results?: Array<{
    username: string;
    title: string;
    status: string;
  }>;
  permissions_set?: boolean;
  topic_renamed?: boolean;
  photo_set?: boolean;
  error?: string;
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

Deno.serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { title, description, photo_url, company_id } = await req.json() as TelegramGroupRequest;

    console.log('Creating Telegram group:', { title, description, company_id });

    // Validate required fields
    if (!title || !description || !company_id) {
      return new Response(
        JSON.stringify({ 
          success: false, 
          error: 'Не указаны обязательные параметры: title, description, company_id' 
        }),
        { 
          status: 400, 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      );
    }

    // Initialize Supabase client early for database checks
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Check if a group with this title and company already exists
    const { data: existingGroups } = await supabaseClient
      .from('telegram_supergroups')
      .select('*')
      .eq('title', title)
      .eq('company_id', company_id)
      .eq('is_active', true);

    if (existingGroups && existingGroups.length > 0) {
      console.log('Group already exists for this company:', existingGroups[0]);
      return new Response(
        JSON.stringify({
          success: true,
          group_data: {
            success: true,
            group_id: Math.abs(existingGroups[0].id),
            group_title: existingGroups[0].title,
            invite_link: existingGroups[0].invite_link,
            existing: true
          },
          message: 'Telegram группа уже существует для этой компании'
        }),
        { 
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      );
    }

    // Call the Telegram microservice with timeout
    let telegramData;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const telegramResponse = await fetch(`${TELEGRAM_MANAGE_URL}/create_group`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title,
          description,
          photo_url
        }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);

      if (!telegramResponse.ok) {
        const errorText = await telegramResponse.text();
        console.error('Telegram API error:', errorText);
        
        return new Response(
          JSON.stringify({ 
            success: false, 
            error: `Ошибка создания группы в Telegram (${telegramResponse.status}): ${errorText}` 
          }),
          { 
            status: 200, // Changed to 200 to avoid automatic error handling
            headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
          }
        );
      }

      telegramData = await telegramResponse.json();
      console.log('Telegram group created:', telegramData);
      
      if (!telegramData.success) {
        return new Response(
          JSON.stringify({ 
            success: false, 
            error: telegramData.error || 'Неизвестная ошибка при создании Telegram группы' 
          }),
          { 
            status: 200,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
          }
        );
      }
    } catch (error) {
      console.error('Error calling Telegram API:', error);
      
      let errorMessage = 'Сервис создания Telegram групп временно недоступен.';
      if (error.name === 'AbortError') {
        errorMessage = 'Превышено время ожидания создания группы. Попробуйте позже.';
      }
      
      return new Response(
        JSON.stringify({ 
          success: false, 
          error: errorMessage 
        }),
        { 
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
        }
      );
    }

    // Save the supergroup data to Supabase
    if (telegramData.success && telegramData.group_id) {
      // Normalize the group ID before saving
      const normalizedGroupId = normalizeTelegramSupergroupId(telegramData.group_id);
      console.log(`Normalizing group ID: ${telegramData.group_id} -> ${normalizedGroupId}`);

      // Use upsert to handle potential duplicates gracefully
      const { data: supergroupData, error: dbError } = await supabaseClient
        .from('telegram_supergroups')
        .upsert({
          id: normalizedGroupId,
          company_id: company_id,
          title: telegramData.group_title || title,
          username: null, // Не возвращается в новом API
          description: description,
          invite_link: telegramData.invite_link,
          member_count: 0, // Начальное значение
          is_forum: true, // Устанавливаем в true для новых групп
          is_active: true,
          bot_is_admin: telegramData.bots_results?.some(bot => bot.status === 'success') || false,
          has_visible_history: true,
          join_to_send_messages: false,
          max_reaction_count: 11,
          metadata: {
            bots_results: telegramData.bots_results,
            permissions_set: telegramData.permissions_set,
            topic_renamed: telegramData.topic_renamed,
            photo_set: telegramData.photo_set
          },
          updated_at: new Date().toISOString()
        })
        .select()
        .single();

      if (dbError) {
        console.error('Database error:', dbError);
        
        // Return success for Telegram creation even if database save fails
        console.log('Telegram group created successfully, but database save failed. Returning success.');
        return new Response(
          JSON.stringify({
            success: true,
            group_data: telegramData,
            message: 'Telegram группа успешно создана (предупреждение: проблема с сохранением в базе данных)'
          }),
          { 
            headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
          }
        );
      }

      console.log('Supergroup saved to database:', supergroupData);
    }

    return new Response(
      JSON.stringify({
        success: true,
        group_data: telegramData,
        message: 'Telegram группа успешно создана и сохранена'
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    );

  } catch (error) {
    console.error('Function error:', error);
    
    return new Response(
      JSON.stringify({ 
        success: false, 
        error: 'Внутренняя ошибка сервера' 
      }),
      { 
        status: 500, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      }
    );
  }
});