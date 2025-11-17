-- Create tg_users table
CREATE TABLE public.tg_users (
  id bigint NOT NULL,
  first_name text NOT NULL,
  last_name text NULL,
  username text NULL,
  language_code text NULL,
  photo_url text NULL,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  phone_number text NULL,
  email text NULL,
  allows_write_to_pm boolean NULL,
  color_scheme text NULL,
  is_premium boolean NULL,
  is_blocked boolean NULL DEFAULT false,
  odoo_partner_id integer NULL,
  odoo_name text NULL,
  odoo_surname text NULL,
  policy boolean NOT NULL DEFAULT false,
  CONSTRAINT tg_users_pkey PRIMARY KEY (id)
);

-- Create index on username
CREATE INDEX IF NOT EXISTS tg_users_username_idx ON public.tg_users USING btree (username);

-- Create trigger for updated_at (only one trigger needed)
CREATE TRIGGER set_tg_users_updated_at 
  BEFORE UPDATE ON public.tg_users 
  FOR EACH ROW 
  EXECUTE FUNCTION public.update_updated_at_column();

-- Enable RLS
ALTER TABLE public.tg_users ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Only admins can view all tg_users
CREATE POLICY "Admins can view all tg_users" 
  ON public.tg_users 
  FOR SELECT 
  USING (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));

-- Only admins can insert tg_users
CREATE POLICY "Admins can insert tg_users" 
  ON public.tg_users 
  FOR INSERT 
  WITH CHECK (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));

-- Only admins can update tg_users
CREATE POLICY "Admins can update tg_users" 
  ON public.tg_users 
  FOR UPDATE 
  USING (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));

-- Only admins can delete tg_users
CREATE POLICY "Admins can delete tg_users" 
  ON public.tg_users 
  FOR DELETE 
  USING (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));