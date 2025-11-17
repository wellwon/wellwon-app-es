-- Create enum for company status
CREATE TYPE public.company_status AS ENUM ('new', 'bronze', 'silver', 'gold');

-- Add new fields to companies table
ALTER TABLE public.companies 
ADD COLUMN status public.company_status NOT NULL DEFAULT 'new',
ADD COLUMN orders_count integer NOT NULL DEFAULT 0,
ADD COLUMN turnover numeric(15,2) NOT NULL DEFAULT 0.00,
ADD COLUMN rating numeric(3,2) NOT NULL DEFAULT 0.0 CHECK (rating >= 0.0 AND rating <= 5.0),
ADD COLUMN successful_deliveries integer NOT NULL DEFAULT 0,
ADD COLUMN average_delivery_time numeric(8,2) NOT NULL DEFAULT 0.0,
ADD COLUMN on_time_delivery_percentage numeric(5,2) NOT NULL DEFAULT 0.0 CHECK (on_time_delivery_percentage >= 0.0 AND on_time_delivery_percentage <= 100.0);

-- Update existing company with some sample data for testing
UPDATE public.companies 
SET 
    status = 'bronze',
    orders_count = 25,
    turnover = 150000.00,
    rating = 4.2,
    successful_deliveries = 23,
    average_delivery_time = 3.5,
    on_time_delivery_percentage = 92.0
WHERE id = 53;