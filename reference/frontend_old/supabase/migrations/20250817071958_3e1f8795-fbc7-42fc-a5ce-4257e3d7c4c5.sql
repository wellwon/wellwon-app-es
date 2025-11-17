-- Add RLS policy to allow users to claim unassigned supergroups
CREATE POLICY "Users can claim unassigned supergroups" 
ON telegram_supergroups 
FOR UPDATE 
USING (company_id IS NULL)
WITH CHECK (company_id IN (
  SELECT uc.company_id
  FROM user_companies uc
  WHERE uc.user_id = auth.uid() AND uc.is_active = true
));