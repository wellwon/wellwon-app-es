-- Добавить поле country как текст в таблицу companies
ALTER TABLE companies 
ADD COLUMN country text DEFAULT 'Россия';

-- Заполнить существующие записи значением по умолчанию
UPDATE companies 
SET country = 'Россия' 
WHERE country IS NULL;