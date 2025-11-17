-- Create storage bucket for message template images
INSERT INTO storage.buckets (id, name, public) VALUES ('message-templates', 'message-templates', true);

-- Create RLS policies for message template images
CREATE POLICY "Template images are publicly viewable" 
ON storage.objects 
FOR SELECT 
USING (bucket_id = 'message-templates');

CREATE POLICY "Authenticated users can upload template images" 
ON storage.objects 
FOR INSERT 
WITH CHECK (bucket_id = 'message-templates' AND auth.role() = 'authenticated');

CREATE POLICY "Users can update template images" 
ON storage.objects 
FOR UPDATE 
USING (bucket_id = 'message-templates' AND auth.role() = 'authenticated');

CREATE POLICY "Users can delete template images" 
ON storage.objects 
FOR DELETE 
USING (bucket_id = 'message-templates' AND auth.role() = 'authenticated');