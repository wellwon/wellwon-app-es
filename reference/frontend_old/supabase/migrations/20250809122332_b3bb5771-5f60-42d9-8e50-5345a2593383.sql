-- Create a server-side function to handle company creation with proper authentication
CREATE OR REPLACE FUNCTION public.create_company_with_owner(
  company_data jsonb,
  owner_user_id uuid
) RETURNS TABLE(
  id bigint,
  name text,
  company_type text,
  vat text,
  ogrn text,
  kpp text,
  director text,
  email text,
  phone text,
  street text,
  city text,
  postal_code text,
  balance numeric,
  status company_status,
  orders_count integer,
  turnover numeric,
  rating numeric,
  successful_deliveries integer,
  created_at timestamp with time zone,
  updated_at timestamp with time zone
) LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  new_company_id bigint;
  company_record record;
BEGIN
  -- Check if user exists and is active
  IF NOT EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE user_id = owner_user_id AND active = true
  ) THEN
    RAISE EXCEPTION 'User not found or inactive';
  END IF;
  
  -- Check for duplicate company by VAT or name
  IF EXISTS (
    SELECT 1 FROM public.companies 
    WHERE (company_data->>'vat' IS NOT NULL AND vat = company_data->>'vat')
       OR (company_data->>'name' IS NOT NULL AND name ILIKE '%' || (company_data->>'name') || '%')
  ) THEN
    RAISE EXCEPTION 'COMPANY_EXISTS';
  END IF;
  
  -- Insert the company
  INSERT INTO public.companies (
    name,
    company_type,
    vat,
    ogrn,
    kpp,
    director,
    email,
    phone,
    street,
    city,
    postal_code,
    created_by_user_id,
    assigned_manager_id,
    balance
  ) VALUES (
    company_data->>'name',
    company_data->>'company_type',
    company_data->>'vat',
    company_data->>'ogrn',
    company_data->>'kpp',
    company_data->>'director',
    company_data->>'email',
    company_data->>'phone',
    company_data->>'street',
    company_data->>'city',
    company_data->>'postal_code',
    owner_user_id,
    owner_user_id,
    0
  ) RETURNING * INTO company_record;
  
  new_company_id := company_record.id;
  
  -- Link the user to the company as owner
  INSERT INTO public.user_companies (
    user_id,
    company_id,
    relationship_type
  ) VALUES (
    owner_user_id,
    new_company_id,
    'owner'
  );
  
  -- Return the created company
  RETURN QUERY
  SELECT 
    company_record.id,
    company_record.name,
    company_record.company_type,
    company_record.vat,
    company_record.ogrn,
    company_record.kpp,
    company_record.director,
    company_record.email,
    company_record.phone,
    company_record.street,
    company_record.city,
    company_record.postal_code,
    company_record.balance,
    company_record.status,
    company_record.orders_count,
    company_record.turnover,
    company_record.rating,
    company_record.successful_deliveries,
    company_record.created_at,
    company_record.updated_at;
END;
$$;