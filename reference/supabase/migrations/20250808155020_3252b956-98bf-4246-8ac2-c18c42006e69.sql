-- Create companies table
CREATE TABLE public.companies (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  vat TEXT,
  ogrn TEXT,
  kpp TEXT,
  postal_code TEXT,
  country_id INTEGER DEFAULT 190,
  director TEXT,
  street TEXT,
  city TEXT,
  email TEXT,
  phone TEXT,
  company_type TEXT NOT NULL DEFAULT 'company',
  tg_dir TEXT,
  tg_accountant TEXT,
  tg_manager_1 TEXT,
  tg_manager_2 TEXT,
  tg_manager_3 TEXT,
  tg_support TEXT,
  balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  x_studio_company_or_project TEXT DEFAULT 'Company'
);

-- Enable RLS
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- Create policies for companies
CREATE POLICY "Admins can view all companies" 
ON public.companies 
FOR SELECT 
USING (get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text]));

CREATE POLICY "Admins can insert companies" 
ON public.companies 
FOR INSERT 
WITH CHECK (get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text]));

CREATE POLICY "Admins can update companies" 
ON public.companies 
FOR UPDATE 
USING (get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text]));

CREATE POLICY "Admins can delete companies" 
ON public.companies 
FOR DELETE 
USING (get_current_user_type() = ANY (ARRAY['ww_developer'::text, 'ww_manager'::text]));

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_companies_updated_at
BEFORE UPDATE ON public.companies
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Create indexes for performance
CREATE INDEX idx_companies_vat ON public.companies(vat);
CREATE INDEX idx_companies_email ON public.companies(email);
CREATE INDEX idx_companies_company_type ON public.companies(company_type);
CREATE INDEX idx_companies_x_studio_type ON public.companies(x_studio_company_or_project);

-- Insert sample data
INSERT INTO public.companies (
  id, name, vat, ogrn, kpp, postal_code, country_id, director, street, city, 
  email, phone, company_type, tg_dir, tg_accountant, tg_manager_1, tg_manager_2, 
  tg_manager_3, balance, created_at, updated_at, tg_support, x_studio_company_or_project
) VALUES 
(9, 'ИП Бабанин Роман Олегович', '200415177603', null, null, '192283', 190, 'Babanin Roman', null, 'Bolshoi Tsaryn', 'tvoi.trand@yandex.ru', null, 'company', null, null, null, null, null, 0.00, '2025-04-05 05:37:18.360108+00', '2025-08-08 12:24:42.606417+00', null, 'Company'),
(25, 'ООО ВЭЛСИГРУПП', '5407024318', null, null, '214006', 190, 'Макаренко Егор Андреевич', 'Чкалова, д. 6 А, офис М 5', 'Смоленск', 'velsi@wellwon.hk', '+375 29 393-58-76', 'company', null, null, null, null, null, 0.00, '2025-04-05 05:37:19.184116+00', '2025-08-08 12:24:44.100899+00', null, 'Company'),
(49, 'PLANET C', null, null, null, null, 190, null, null, null, null, null, 'company', null, null, null, null, null, 0.00, '2025-04-05 05:37:18.042314+00', '2025-08-08 12:24:42.128031+00', null, 'Project'),
(50, 'AUSBEN', null, null, null, null, 190, null, null, null, null, null, 'company', null, null, null, null, null, 0.00, '2025-04-05 05:37:17.690842+00', '2025-08-08 12:24:41.617849+00', null, 'Project'),
(52, 'TvoyTrand', null, null, null, null, 190, null, null, null, null, null, 'company', null, null, null, null, null, 0.00, '2025-04-05 05:37:18.152433+00', '2025-08-08 12:24:42.302624+00', null, 'Project');

-- Reset sequence to continue from the highest ID
SELECT setval('companies_id_seq', (SELECT MAX(id) FROM companies));