-- Add logo_url column to companies table
ALTER TABLE public.companies 
ADD COLUMN logo_url text;

-- Create Company_Logo storage bucket
INSERT INTO storage.buckets (id, name, public) 
VALUES ('company-logos', 'company-logos', true);

-- Create RLS policies for company logo uploads
CREATE POLICY "Anyone can view company logos" 
ON storage.objects 
FOR SELECT 
USING (bucket_id = 'company-logos');

CREATE POLICY "Authenticated users can upload company logos" 
ON storage.objects 
FOR INSERT 
WITH CHECK (
  bucket_id = 'company-logos' 
  AND auth.uid() IS NOT NULL
);

CREATE POLICY "Users can update their company logos" 
ON storage.objects 
FOR UPDATE 
USING (
  bucket_id = 'company-logos' 
  AND auth.uid() IS NOT NULL
);

CREATE POLICY "Users can delete their company logos" 
ON storage.objects 
FOR DELETE 
USING (
  bucket_id = 'company-logos' 
  AND auth.uid() IS NOT NULL
);