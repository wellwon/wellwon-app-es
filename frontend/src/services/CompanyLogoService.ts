// Stub service - will be replaced with Storage service API
// Reference: /reference/frontend_old/src/services/CompanyLogoService.ts

class CompanyLogoServiceClass {
  async uploadLogo(companyId: number, file: File): Promise<string | null> {
    console.warn('[STUB] CompanyLogoService.uploadLogo - Storage service not implemented yet');
    return null;
  }

  async deleteLogo(companyId: number): Promise<boolean> {
    console.warn('[STUB] CompanyLogoService.deleteLogo - Storage service not implemented yet');
    return false;
  }

  async deleteByUrl(url: string): Promise<boolean> {
    console.warn('[STUB] CompanyLogoService.deleteByUrl - Storage service not implemented yet');
    return false;
  }

  getLogoUrl(companyId: number): string {
    console.warn('[STUB] CompanyLogoService.getLogoUrl - Storage service not implemented yet');
    return '';
  }

  validateImage(file: File): { valid: boolean; error?: string } {
    console.warn('[STUB] CompanyLogoService.validateImage - Storage service not implemented yet');
    return { valid: true };
  }

  async processAndUpload(companyId: number, file: File): Promise<string | null> {
    console.warn('[STUB] CompanyLogoService.processAndUpload - Storage service not implemented yet');
    return null;
  }

  async getImageFromClipboard(): Promise<File | null> {
    console.warn('[STUB] CompanyLogoService.getImageFromClipboard - Storage service not implemented yet');
    return null;
  }
}

export const CompanyLogoService = new CompanyLogoServiceClass();
export default CompanyLogoService;
