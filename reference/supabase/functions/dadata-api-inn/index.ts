import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

const DADATA_API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party";

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: corsHeaders
    });
  }

  try {
    const { vat } = await req.json();
    
    // Валидация ИНН
    if (!vat || vat.length < 10) {
      return new Response(JSON.stringify({
        error: 'ИНН должен содержать минимум 10 символов'
      }), {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        },
        status: 400
      });
    }

    const DADATA_API_KEY = Deno.env.get('DADATA_API_KEY');
    const DADATA_SECRET_KEY = Deno.env.get('DADATA_SECRET_KEY');

    // Проверяем наличие ключей API
    if (!DADATA_API_KEY || !DADATA_SECRET_KEY) {
      console.error('DADATA API keys are not properly configured');
      return new Response(JSON.stringify({
        error: 'DADATA API keys are not properly configured'
      }), {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        },
        status: 500
      });
    }

    // Скрываем секретные ключи в логах
    console.log('Making request to DaData API for INN:', vat);
    console.log('Request payload:', { query: vat });

    const response = await fetch(DADATA_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': `Token ${DADATA_API_KEY}`,
        'X-Secret': DADATA_SECRET_KEY
      },
      body: JSON.stringify({
        query: vat
      })
    });

    if (!response.ok) {
      console.error('DaData API returned error:', response.status, response.statusText);
      return new Response(JSON.stringify({
        error: `DaData API error: ${response.status} ${response.statusText}`
      }), {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        },
        status: response.status
      });
    }

    const data = await response.json();

    // Логируем информацию о директоре для отладки
    if (data.suggestions && data.suggestions[0]) {
      const company = data.suggestions[0].data;
      console.log('Company data received:', {
        name: company.name?.full_with_opf,
        inn: company.inn,
        kpp: company.kpp,
        ogrn: company.ogrn
      });
      
      if (company.management) {
        console.log('Management data found:', company.management.name);
      }
      if (company.managers && company.managers.length > 0) {
        console.log('Managers data found:', company.managers[0].name);
      }
    } else {
      console.log('No company data found for INN:', vat);
    }

    return new Response(JSON.stringify(data), {
      headers: {
        ...corsHeaders,
        'Content-Type': 'application/json'
      }
    });

  } catch (error) {
    console.error('DaData API error:', error.message);
    return new Response(JSON.stringify({
      error: error.message
    }), {
      headers: {
        ...corsHeaders,
        'Content-Type': 'application/json'
      },
      status: 500
    });
  }
});