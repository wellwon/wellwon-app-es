-- Create news table
CREATE TABLE public.news (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  title text NOT NULL,
  content text NOT NULL,
  date timestamp with time zone NOT NULL DEFAULT now(),
  category text NOT NULL,
  image text NULL,
  is_published boolean NULL DEFAULT true,
  created_at timestamp with time zone NULL DEFAULT now(),
  updated_at timestamp with time zone NULL DEFAULT now(),
  preview text NULL,
  CONSTRAINT news_pkey PRIMARY KEY (id)
);

-- Create trigger for updated_at
CREATE TRIGGER set_updated_at 
  BEFORE UPDATE ON public.news 
  FOR EACH ROW 
  EXECUTE FUNCTION public.update_updated_at_column();

-- Enable RLS
ALTER TABLE public.news ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Anyone can view published news
CREATE POLICY "Anyone can view published news" 
  ON public.news 
  FOR SELECT 
  USING (is_published = true);

-- Only admins can insert news
CREATE POLICY "Admins can insert news" 
  ON public.news 
  FOR INSERT 
  WITH CHECK (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));

-- Only admins can update news
CREATE POLICY "Admins can update news" 
  ON public.news 
  FOR UPDATE 
  USING (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));

-- Only admins can delete news
CREATE POLICY "Admins can delete news" 
  ON public.news 
  FOR DELETE 
  USING (get_current_user_type() = ANY (ARRAY['ww_manager'::text, 'ww_developer'::text]));