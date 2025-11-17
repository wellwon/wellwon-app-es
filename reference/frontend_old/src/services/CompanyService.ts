import { supabase } from '@/integrations/supabase/client';
import type { Company } from '@/types/realtime-chat';
import { logger } from '@/utils/logger';

export class CompanyService {
  // Проверить существование компании по ИНН или названию
  static async checkCompanyExists(vat?: string, name?: string): Promise<boolean> {
    try {
      if (!vat && !name) return false;
      
      // Нормализуем данные для сравнения
      const normalizedVat = vat?.trim();
      const normalizedName = name?.trim();
      
      if (!normalizedVat && !normalizedName) return false;
      
      logger.debug('Checking company existence', { 
        vat: normalizedVat, 
        name: normalizedName,
        component: 'CompanyService' 
      });
      
      let query = supabase.from('companies').select('id, name, vat');
      
      // Строим условие поиска
      const conditions = [];
      if (normalizedVat) {
        conditions.push(`vat.eq."${normalizedVat}"`);
      }
      if (normalizedName) {
        // Точное совпадение по названию (регистронезависимое)
        conditions.push(`name.ilike."${normalizedName}"`);
      }
      
      if (conditions.length > 0) {
        query = query.or(conditions.join(','));
      }
      
      const { data, error } = await query;

      if (error) {
        logger.error('Error checking company existence', error, { component: 'CompanyService' });
        return false;
      }

      const exists = !!data && data.length > 0;
      logger.debug('Company existence check result', { 
        exists, 
        foundCompanies: data?.length || 0,
        component: 'CompanyService' 
      });

      return exists;
    } catch (error) {
      logger.error('Error in checkCompanyExists', error, { component: 'CompanyService' });
      return false;
    }
  }
  // Получить компанию пользователя (активную)
  static async getUserCompany(userId: string): Promise<Company | null> {
    try {
      logger.debug('CompanyService.getUserCompany called', { userId, component: 'CompanyService' });
      
      // Используем только user_companies для всех пользователей
      const { data, error } = await supabase
        .from('user_companies')
        .select(`
          company_id,
          companies (
            id, name, company_type, balance, status, orders_count, 
            turnover, rating, successful_deliveries, created_at, updated_at
          )
        `)
        .eq('user_id', userId)
        .eq('is_active', true)
        .eq('relationship_type', 'owner')
        .order('assigned_at', { ascending: false })
        .limit(1);
      
      logger.debug('user_companies response', { hasData: !!data, error: !!error, component: 'CompanyService' });
      
      if (error) {
        logger.error('Error loading user company', error, { component: 'CompanyService' });
        return null;
      }
      
      // data is now an array, get the first company
      const result = data && data.length > 0 ? data[0].companies : null;
      logger.debug('getUserCompany result', { hasResult: !!result, component: 'CompanyService' });
      return result;
    } catch (error) {
      logger.error('Error in getUserCompany', error, { component: 'CompanyService' });
      return null;
    }
  }

  // Получить все компании пользователя
  static async getUserCompanies(userId: string): Promise<(Company & { relationship_type: string })[]> {
    try {
      logger.debug('CompanyService.getUserCompanies called', { userId, component: 'CompanyService' });
      
      const { data, error } = await supabase
        .from('user_companies')
        .select(`
          relationship_type,
          companies (
            id, name, company_type, balance, status, orders_count, 
            turnover, rating, successful_deliveries, created_at, updated_at
          )
        `)
        .eq('user_id', userId)
        .eq('is_active', true)
        .order('assigned_at', { ascending: false });
      
      logger.debug('user_companies (multiple) response', { hasData: !!data, error: !!error, component: 'CompanyService' });
      
      if (error) {
        logger.error('Error loading user companies', error, { component: 'CompanyService' });
        return [];
      }
      
      const result = data?.map(item => ({
        ...(item.companies as Company),
        relationship_type: item.relationship_type
      })).filter(Boolean) || [];
      
      logger.debug('getUserCompanies result', { companiesCount: result.length, component: 'CompanyService' });
      return result;
    } catch (error) {
      logger.error('Error in getUserCompanies', error, { component: 'CompanyService' });
      return [];
    }
  }

  // Создать компанию
  static async createCompany(
    companyData: {
      name: string;
      company_type: string;
      vat?: string;
      ogrn?: string;
      kpp?: string;
      director?: string;
      email?: string;
      phone?: string;
      street?: string;
      city?: string;
      postal_code?: string;
      country?: string;
      logo_url?: string;
    },
    createdByUserId: string,
    assignToUserId?: string // Пользователь, к которому привязать компанию (для админов)
  ): Promise<Company> {
    try {
      logger.info('CompanyService.createCompany starting', { 
        companyName: companyData.name, 
        createdByUserId, 
        assignToUserId,
        component: 'CompanyService'
      });

      // Определяем кому назначить компанию
      const userToAssign = assignToUserId || createdByUserId;
      
      logger.debug('Using server-side function to create company', { 
        user_id: userToAssign, 
        companyData,
        isForClient: !!assignToUserId,
        component: 'CompanyService'
      });
      
      // Логируем точные данные которые передаем в RPC функцию
      logger.info('Calling create_company_with_owner with data', {
        company_data: companyData,
        owner_user_id: userToAssign,
        component: 'CompanyService'
      });

      // Используем серверную функцию для создания компании
      const { data, error } = await supabase
        .rpc('create_company_with_owner', {
          company_data: companyData,
          owner_user_id: userToAssign
        });

      if (error) {
        logger.error('Error creating company with server function', error, { component: 'CompanyService' });
        throw error;
      }

      if (!data || data.length === 0) {
        throw new Error('No company data returned from server function');
      }

      const company = data[0];
      logger.info('Company created successfully', { companyId: company.id, companyName: company.name, component: 'CompanyService' });
      
      // Если это первая компания пользователя, привязываем все его существующие чаты к ней
      try {
        const { data: userCompaniesCount } = await supabase
          .from('user_companies')
          .select('id', { count: 'exact' })
          .eq('user_id', userToAssign)
          .eq('is_active', true);
        
        const isFirstCompany = !userCompaniesCount || userCompaniesCount.length <= 1;
        
        if (isFirstCompany) {
          logger.debug('This is the first company, binding existing chats...', { component: 'CompanyService' });
          const { error: bindError } = await supabase.rpc('bind_client_chats_to_first_company', {
            client_user_id: userToAssign,
            company_uuid: company.id
          });
          
          if (bindError) {
            logger.warn('Error binding existing chats to first company', { bindError, component: 'CompanyService' });
          } else {
            logger.debug('Successfully bound existing chats to first company', { component: 'CompanyService' });
          }
        }
      } catch (error) {
        logger.warn('Error checking/binding existing chats', { error, component: 'CompanyService' });
      }
      
      logger.info('Company creation completed successfully', { component: 'CompanyService' });
      
      return company;
    } catch (error) {
      logger.error('Error in createCompany', error, { component: 'CompanyService' });
      throw error;
    }
  }

  // Получить всех сотрудников компании
  static async getCompanyEmployees(companyId: number) {
    try {
      const { data, error } = await supabase
        .from('user_companies')
        .select(`
          user_id,
          relationship_type,
          profiles (
            user_id, first_name, last_name, avatar_url, type, active
          )
        `)
        .eq('company_id', companyId)
        .eq('is_active', true);

      if (error) throw error;
      
      // Преобразуем в формат profiles для обратной совместимости
      return data?.map(uc => {
        if (!uc.profiles) return null;
        const profile = uc.profiles as any;
        return {
          user_id: profile.user_id,
          first_name: profile.first_name,
          last_name: profile.last_name,
          avatar_url: profile.avatar_url,
          type: profile.type,
          active: profile.active,
          role_in_company: uc.relationship_type
        };
      }).filter(Boolean) || [];
    } catch (error) {
      logger.error('Error getting company employees', error, { component: 'CompanyService' });
      throw error;
    }
  }

  // Получить компанию по ID
  static async getCompanyById(companyId: number): Promise<Company | null> {
    try {
      const { data, error } = await supabase
        .from('companies')
        .select('*')
        .eq('id', companyId)
        .single();

      if (error) {
        if (error.code === 'PGRST116') { // No rows returned
          return null;
        }
        throw error;
      }
      
      return data;
    } catch (error) {
      logger.error('Error getting company by ID', error, { component: 'CompanyService' });
      return null;
    }
  }

  // Обновить компанию
  static async updateCompany(companyId: number, updates: Partial<Company>) {
    try {
      // Фильтруем logo_url из обновлений, так как оно больше не используется
      const { logo_url, ...cleanUpdates } = updates;
      
      const { data, error } = await supabase
        .from('companies')
        .update(cleanUpdates)
        .eq('id', companyId)
        .select()
        .single();

      if (error) throw error;
      logger.info('Company updated successfully', { companyId, updates: cleanUpdates, component: 'CompanyService' });
      return data;
    } catch (error) {
      logger.error('Error updating company', error, { component: 'CompanyService' });
      throw error;
    }
  }
}