// Stub service - will be replaced with Company domain API
// Reference: /reference/frontend_old/src/services/CompanyService.ts

export interface Company {
  id: number;
  name: string;
  description?: string;
  vat?: string;
  ogrn?: string;
  kpp?: string;
  email?: string;
  phone?: string;
  company_type?: string;
  status: 'active' | 'inactive' | 'suspended';
  created_at: string;
  updated_at: string;
}

export interface UserCompany {
  id: string;
  user_id: string;
  company_id: number;
  relationship_type: 'owner' | 'manager' | 'assigned_admin';
  is_active: boolean;
  created_at: string;
}

class CompanyServiceClass {
  async getUserCompanies(userId: string): Promise<UserCompany[]> {
    console.warn('[STUB] CompanyService.getUserCompanies - Company domain not implemented yet');
    return [];
  }

  async getCompanyById(companyId: number): Promise<Company | null> {
    console.warn('[STUB] CompanyService.getCompanyById - Company domain not implemented yet');
    return null;
  }

  async getCompanies(): Promise<Company[]> {
    console.warn('[STUB] CompanyService.getCompanies - Company domain not implemented yet');
    return [];
  }

  async createCompany(data: Partial<Company>): Promise<Company | null> {
    console.warn('[STUB] CompanyService.createCompany - Company domain not implemented yet');
    return null;
  }

  async updateCompany(companyId: number, data: Partial<Company>): Promise<Company | null> {
    console.warn('[STUB] CompanyService.updateCompany - Company domain not implemented yet');
    return null;
  }

  async deleteCompany(companyId: number): Promise<boolean> {
    console.warn('[STUB] CompanyService.deleteCompany - Company domain not implemented yet');
    return false;
  }

  async addUserToCompany(userId: string, companyId: number, role: string): Promise<boolean> {
    console.warn('[STUB] CompanyService.addUserToCompany - Company domain not implemented yet');
    return false;
  }

  async checkCompanyExists(vat: string): Promise<boolean> {
    console.warn('[STUB] CompanyService.checkCompanyExists - Company domain not implemented yet');
    return false;
  }
}

export const CompanyService = new CompanyServiceClass();
export default CompanyService;
