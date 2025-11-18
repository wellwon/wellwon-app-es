export interface CompanyFormData {
  id?: string | number;
  vat: string;                 // ИНН
  kpp: string;                 // КПП
  ogrn: string;                // ОГРН
  company_name: string;        // Название компании
  email: string;               // Email
  phone: string;               // Телефон
  street: string;              // Адрес (улица)
  city: string;                // Город
  postal_code: string;         // Индекс
  country: string;             // Страна
  director: string;            // Директор
  company_type: string;        // Тип компании
  logo_url?: string;           // URL логотипа
}

export interface SupergroupFormData {
  id?: number;
  title: string;
  description: string;
  username?: string;
  invite_link?: string;
  member_count?: number;
  is_forum?: boolean;
  company_id?: number;
  company_logo?: string;
  group_type?: 'client' | 'payments' | 'logistics' | 'buyers' | 'others' | 'wellwon';
}

export interface FormValidationErrors {
  [key: string]: string;
}