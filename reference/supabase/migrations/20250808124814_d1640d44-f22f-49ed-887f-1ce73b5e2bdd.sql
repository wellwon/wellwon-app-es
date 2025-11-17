-- Create message_templates table
CREATE TABLE public.message_templates (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  template_data JSONB NOT NULL,
  image_url TEXT,
  created_by UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  is_active BOOLEAN NOT NULL DEFAULT true
);

-- Enable Row Level Security
ALTER TABLE public.message_templates ENABLE ROW LEVEL SECURITY;

-- Create policies for message templates
CREATE POLICY "Admins can manage all templates"
ON public.message_templates
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM public.profiles
    WHERE user_id = auth.uid()
    AND type IN ('ww_manager', 'ww_developer')
  )
);

CREATE POLICY "Users can view active templates"
ON public.message_templates
FOR SELECT
USING (is_active = true);

CREATE POLICY "Creators can update their templates"
ON public.message_templates
FOR UPDATE
USING (created_by = auth.uid());

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_message_templates_updated_at
BEFORE UPDATE ON public.message_templates
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Insert existing templates from the codebase
INSERT INTO public.message_templates (name, description, category, template_data, is_active) VALUES
-- Основные templates
('Активация аккаунта', 'Активируем ваш аккаунт через Telegram для быстрого доступа к платформе WellWon', 'основные', '{"type": "interactive", "title": "Активирую ваш аккаунт", "description": "Активируем ваш аккаунт через Telegram для быстрого доступа к платформе WellWon", "buttons": [{"text": "🔐 Получить код", "action": "get_activation_code"}]}', true),

('Приветствие', 'Добро пожаловать на платформу WellWon! Мы поможем вам с логистикой.', 'основные', '{"type": "interactive", "title": "Добро пожаловать!", "description": "Добро пожаловать на платформу WellWon! Мы поможем вам с логистикой.", "buttons": [{"text": "🚀 Начать работу", "action": "start_onboarding"}, {"text": "📞 Связаться с менеджером", "action": "contact_manager"}]}', true),

('Подтверждение заявки', 'Ваша заявка принята и находится в обработке', 'основные', '{"type": "interactive", "title": "Заявка принята", "description": "Ваша заявка принята и находится в обработке. Мы свяжемся с вами в ближайшее время.", "buttons": [{"text": "📋 Статус заявки", "action": "check_status"}, {"text": "✏️ Изменить заявку", "action": "edit_request"}]}', true),

-- Поиск товара templates
('Поиск товара', 'Поможем найти нужный товар в Китае', 'поиск товара', '{"type": "interactive", "title": "Поиск товара в Китае", "description": "Поможем найти нужный товар в Китае по лучшей цене", "buttons": [{"text": "🔍 Начать поиск", "action": "start_search"}, {"text": "📸 Загрузить фото", "action": "upload_photo"}]}', true),

('Результат поиска', 'Найдены подходящие товары по вашему запросу', 'поиск товара', '{"type": "interactive", "title": "Товары найдены", "description": "Найдены подходящие товары по вашему запросу", "buttons": [{"text": "👀 Посмотреть", "action": "view_products"}, {"text": "💰 Узнать цену", "action": "get_price"}]}', true),

-- Финансы templates
('Расчет стоимости', 'Рассчитаем полную стоимость доставки вашего груза', 'финансы', '{"type": "interactive", "title": "Расчет стоимости", "description": "Рассчитаем полную стоимость доставки вашего груза", "buttons": [{"text": "💵 Получить расчет", "action": "calculate_cost"}, {"text": "📊 Детализация", "action": "detailed_breakdown"}]}', true),

('Оплата', 'Выберите удобный способ оплаты', 'финансы', '{"type": "interactive", "title": "Способ оплаты", "description": "Выберите удобный способ оплаты", "buttons": [{"text": "💳 Картой", "action": "pay_card"}, {"text": "🏦 Переводом", "action": "pay_transfer"}]}', true),

-- Логистика templates
('Статус доставки', 'Актуальная информация о вашем грузе', 'логистика', '{"type": "interactive", "title": "Статус груза", "description": "Актуальная информация о вашем грузе", "buttons": [{"text": "📍 Где груз?", "action": "track_cargo"}, {"text": "📅 Время прибытия", "action": "delivery_time"}]}', true),

('Оформление груза', 'Помощь в оформлении документов на груз', 'логистика', '{"type": "interactive", "title": "Оформление документов", "description": "Помощь в оформлении документов на груз", "buttons": [{"text": "📄 Начать оформление", "action": "start_documentation"}, {"text": "❓ Нужна помощь", "action": "need_help"}]}', true),

-- Последняя миля templates
('Доставка до двери', 'Организуем доставку груза до вашего склада или офиса', 'последняя миля', '{"type": "interactive", "title": "Доставка до двери", "description": "Организуем доставку груза до вашего склада или офиса", "buttons": [{"text": "🚚 Заказать доставку", "action": "order_delivery"}, {"text": "⏰ Выбрать время", "action": "schedule_delivery"}]}', true),

('Получение груза', 'Инструкции по получению вашего груза', 'последняя миля', '{"type": "interactive", "title": "Получение груза", "description": "Инструкции по получению вашего груза", "buttons": [{"text": "📋 Что нужно?", "action": "delivery_requirements"}, {"text": "📞 Связаться с курьером", "action": "contact_courier"}]}', true);