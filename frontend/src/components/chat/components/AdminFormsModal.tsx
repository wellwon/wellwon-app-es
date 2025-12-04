import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Loader2, Building, X, CheckCircle, XCircle, Copy, Check } from 'lucide-react';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { CompanyFormData, FormValidationErrors } from '@/types/company-form';
import { CompanyInfoFields } from './forms/CompanyInfoFields';
import { AddressFields } from './forms/AddressFields';
import { ContactInfoFields } from './forms/ContactInfoFields';
import { FormActions } from './forms/FormActions';
import { TelegramGroupFields } from './forms/TelegramGroupFields';
import { Switch } from '@/components/ui/switch';
import { API } from '@/api/core';
import { Label } from '@/components/ui/label';
import { FormSection } from '@/components/design-system/FormSection';
import { GlassCard, GlassButton } from '@/components/design-system';
import * as companyApi from '@/api/company';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { logger } from '@/utils/logger';

// Константа URL логотипа для Telegram групп
// TODO: Move this to backend config or environment variable
const TELEGRAM_GROUP_LOGO_URL = '/api/static/telegram-group-logo.png';

interface AdminFormsModalProps {
  isOpen: boolean;
  onClose: () => void;
  formType: string | null;
  onSuccess?: () => void;
}
export const AdminFormsModal: React.FC<AdminFormsModalProps> = ({
  isOpen,
  onClose,
  formType,
  onSuccess
}) => {
  const {
    activeChat,
    loadCompanyForChat,
    clearCompanyCache
  } = useRealtimeChatContext();
  const {
    user
  } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(true);
  const [errors, setErrors] = useState<FormValidationErrors>({});
  const [isSearching, setIsSearching] = useState(false);
  const [isProject, setIsProject] = useState(false);
  const [showingProcess, setShowingProcess] = useState(false);
  const [processSteps, setProcessSteps] = useState<string[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepStatuses, setStepStatuses] = useState<('pending' | 'loading' | 'success' | 'error')[]>([]);
  const [processError, setProcessError] = useState<string>('');
  const [groupCreationResult, setGroupCreationResult] = useState<any>(null);
  const [createdCompanyData, setCreatedCompanyData] = useState<any>(null);
  const [foundDuplicateCompany, setFoundDuplicateCompany] = useState<companyApi.CompanyDetail | null>(null);
  const [telegramGroupData, setTelegramGroupData] = useState({
    title: '',
    description: 'Рабочая группа WellWon Logistics'
  });
  const [companyFormData, setCompanyFormData] = useState<CompanyFormData>({
    vat: '',
    kpp: '',
    ogrn: '',
    company_name: '',
    email: '',
    phone: '',
    street: '',
    city: '',
    postal_code: '',
    country: '',
    director: '',
    company_type: ''
  });

  // Update Telegram group title when company name changes
  useEffect(() => {
    if (companyFormData.company_name) {
      setTelegramGroupData(prev => ({
        ...prev,
        title: companyFormData.company_name
      }));
    }
  }, [companyFormData.company_name]);
  const [copiedStates, setCopiedStates] = useState<{[key: string]: boolean}>({});

  // Функция копирования с визуальной обратной связью
  const handleCopyClick = async (text: string, buttonId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedStates(prev => ({ ...prev, [buttonId]: true }));
      setTimeout(() => {
        setCopiedStates(prev => ({ ...prev, [buttonId]: false }));
      }, 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  // Валидация форм
  const validateCompanyForm = (data: CompanyFormData): FormValidationErrors => {
    const newErrors: FormValidationErrors = {};
    
    // Обязательное поле для всех типов
    if (!data.company_name || data.company_name.length < 2) {
      newErrors.company_name = isProject ? 'Название проекта обязательно' : 'Название компании обязательно';
    }
    
    // Валидация только для компаний (не проектов)
    if (!isProject) {
      if (!data.vat || data.vat.length < 10) {
        newErrors.vat = 'ИНН должен содержать минимум 10 символов';
      }
      if (!data.kpp || data.kpp.length < 9) {
        newErrors.kpp = 'КПП должен содержать минимум 9 символов';
      }
      if (!data.ogrn || data.ogrn.length < 13) {
        newErrors.ogrn = 'ОГРН должен содержать минимум 13 символов';
      }
      if (!data.street || data.street.length < 2) {
        newErrors.street = 'Адрес должен содержать минимум 2 символа';
      }
      if (!data.city || data.city.length < 2) {
        newErrors.city = 'Город должен содержать минимум 2 символа';
      }
      if (data.postal_code && data.postal_code.length < 5) {
        newErrors.postal_code = 'Индекс должен содержать минимум 5 символов';
      }
    }
    
    return newErrors;
  };

  // Цветовые индикаторы для полей
  const getFieldIndicatorColor = (fieldName: string): string => {
    if (errors[fieldName]) return 'border-l-destructive';
    return 'border-l-accent-red/30';
  };

  // Toggle project mode
  const handleProjectToggle = (checked: boolean) => {
    setIsProject(checked);
    if (checked) {
      // Clear company-specific fields when switching to project mode
      setCompanyFormData({
        ...companyFormData,
        vat: '',
        kpp: '',
        ogrn: '',
        director: '',
        company_type: '',
        postal_code: ''
      });
    }
    setErrors({});
  };

  // Функция поиска по ИНН (нужно реализовать)
  const handleSearchByINN = async () => {
    if (!companyFormData.vat) {
      return;
    }
    const vatValue = companyFormData.vat;

    // Валидация ИНН
    const isValidVatNumber = (vat: string): boolean => {
      return /^\d{10,12}$/.test(vat);
    };
    if (!isValidVatNumber(vatValue)) {
      setErrors(prev => ({
        ...prev,
        vat: 'ИНН должен содержать от 10 до 12 цифр'
      }));
      return;
    }
    setIsSearching(true);
    setErrors(prev => ({
      ...prev,
      vat: ''
    }));
    try {
      // Call DaData API via backend
      const { data } = await API.post<{
        found: boolean;
        inn?: string;
        kpp?: string;
        ogrn?: string;
        name_short_with_opf?: string;
        address?: string;
        director_name?: string;
        emails?: string[];
      }>('/companies/lookup-vat', { vat: vatValue });

      if (!data || !data.found) {
        setErrors(prev => ({
          ...prev,
          vat: 'Компания с таким ИНН не найдена'
        }));
        return;
      }

      // Extract city from address (format: "г Москва, ул Ленина, д 1")
      let city = '';
      let street = data.address || '';
      if (street) {
        // Try to extract city
        const cityMatch = street.match(/^г\s+([^,]+)/i);
        if (cityMatch) {
          city = cityMatch[1].trim();
        }
        // Extract street part (after city)
        const streetIndex = street.toLowerCase().indexOf('ул');
        if (streetIndex !== -1) {
          street = street.substring(streetIndex);
        }
      }

      // Update form with found data
      const newFormData = {
        ...companyFormData,
        vat: data.inn || vatValue,
        company_name: data.name_short_with_opf || companyFormData.company_name,
        ogrn: data.ogrn || companyFormData.ogrn,
        kpp: data.kpp || companyFormData.kpp,
        email: data.emails?.[0] || companyFormData.email,
        city: city || companyFormData.city,
        street: street || companyFormData.street,
        director: data.director_name || companyFormData.director,
        country: 'Россия',
      };

      setCompanyFormData(newFormData);

      // Update Telegram group title when company name is loaded
      setTelegramGroupData(prevGroup => ({
        ...prevGroup,
        title: newFormData.company_name || prevGroup.title
      }));

      logger.info('Company data loaded from DaData', {
        inn: data.inn,
        name: data.name_short_with_opf,
        component: 'AdminFormsModal'
      });
    } catch (error) {
      logger.error('DaData lookup failed', error, { component: 'AdminFormsModal' });
      setErrors(prev => ({
        ...prev,
        vat: 'Ошибка при поиске компании'
      }));
    } finally {
      setIsSearching(false);
    }
  };

  // Обработчики действий
  const handleCancel = () => {
    if (showingProcess) {
      setShowingProcess(false);
      setProcessError('');
      setGroupCreationResult(null);
      setCreatedCompanyData(null);
    } else {
      onClose();
    }
  };

  // Обработчик закрытия процесса
  const handleProcessClose = () => {
    setShowingProcess(false);
    setProcessError('');
    setGroupCreationResult(null);
    setCreatedCompanyData(null);
    onClose();
  };
  const updateStepStatus = (stepIndex: number, status: 'loading' | 'success' | 'error') => {
    setStepStatuses(prev => {
      const newStatuses = [...prev];
      newStatuses[stepIndex] = status;
      return newStatuses;
    });
    if (status === 'success') {
      setCurrentStep(Math.min(stepIndex + 1, processSteps.length - 1));
    }
  };

  // Handler for linking to existing company instead of creating new
  const handleLinkToExistingCompany = async () => {
    if (!foundDuplicateCompany || !user) return;

    setFoundDuplicateCompany(null); // Close the dialog

    try {
      // Continue with saga steps 2-4 but for existing company
      // We need to create Telegram group and link it to existing company
      updateStepStatus(1, 'loading');

      logger.info('Linking to existing company with new Telegram group', {
        companyId: foundDuplicateCompany.id,
        companyName: foundDuplicateCompany.name
      });

      // For existing company, we need to:
      // 1. Create a new Telegram group for the company
      // 2. Link it to the existing company
      // This is done via create_telegram_group API
      await companyApi.createTelegramGroup(
        foundDuplicateCompany.id,
        foundDuplicateCompany.name
      );

      // OPTIMISTIC UI: Dispatch companyCreated event for instant UI update
      window.dispatchEvent(new CustomEvent('companyCreated', {
        detail: {
          company_id: foundDuplicateCompany.id,
          id: foundDuplicateCompany.id,
          name: foundDuplicateCompany.name,
          company_name: foundDuplicateCompany.name,
          company_type: foundDuplicateCompany.company_type || 'company',
          created_at: new Date().toISOString(),
          logo_url: null,
        }
      }));

      logger.info('Dispatched companyCreated event for linked company', {
        companyId: foundDuplicateCompany.id,
        companyName: foundDuplicateCompany.name
      });

      updateStepStatus(1, 'success');
      updateStepStatus(2, 'success');
      updateStepStatus(3, 'success');

      // Clear and reload cache if we had an active chat
      if (activeChat?.id) {
        clearCompanyCache(activeChat.id);
        await loadCompanyForChat(activeChat.id);
      }

      setGroupCreationResult({
        success: true,
        telegram_group_id: null,
        title: foundDuplicateCompany.name,
        invite_link: null,
        group_data: {
          group_title: foundDuplicateCompany.name,
        }
      });
      setCreatedCompanyData(foundDuplicateCompany);

      logger.info('Successfully linked to existing company', {
        companyId: foundDuplicateCompany.id
      });

      if (onSuccess) {
        onSuccess();
      }
    } catch (error: any) {
      logger.error('Error linking to existing company', error);
      // Handle Pydantic validation errors (422) which return array of objects
      let errorMessage = 'Ошибка при привязке к существующей компании';
      const detail = error?.response?.data?.detail;
      if (Array.isArray(detail)) {
        // Pydantic validation error - extract messages
        errorMessage = detail.map((d: any) => d.msg || String(d)).join(', ');
      } else if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (error?.message) {
        errorMessage = error.message;
      }
      setProcessError(errorMessage);
      updateStepStatus(1, 'error');
    }
  };

  // Handler to dismiss duplicate dialog and create new company anyway
  const handleCreateNewAnyway = () => {
    setFoundDuplicateCompany(null);
    // User chose to dismiss, just close the process
    setShowingProcess(false);
  };
  const startCompanyCreation = async () => {
    try {
      // Шаг 1: Проверка дубликатов
      updateStepStatus(0, 'loading');
      logger.info('Starting company creation process', {
        companyName: companyFormData.company_name,
        userId: user?.id,
        activeChat: activeChat?.id,
        isProject
      });

      // Проверяем дубликаты используя companyApi
      const vatValue = companyFormData.vat;
      const companyName = companyFormData.company_name;

      logger.debug('Checking for duplicate company', {
        vat: vatValue,
        name: companyName,
        isProject,
        component: 'AdminFormsModal'
      });

      // Check for duplicates by VAT (companies) or name (projects)
      let existingCompany: companyApi.CompanyDetail | null = null;
      try {
        if (isProject) {
          // For projects: check by exact name match with type 'project'
          if (companyName) {
            const searchResults = await companyApi.searchCompanies(companyName, 5);
            // Find exact name match with project type
            const projectMatch = searchResults.find(
              c => c.name.toLowerCase() === companyName.toLowerCase() && c.company_type === 'project'
            );
            if (projectMatch) {
              existingCompany = await companyApi.getCompanyById(projectMatch.id);
            }
          }
        } else {
          // For companies: check by VAT (INN) first
          if (vatValue) {
            existingCompany = await companyApi.getCompanyByVat(vatValue);
          }
          // Also check by name if no VAT match
          if (!existingCompany && companyName) {
            const searchResults = await companyApi.searchCompanies(companyName, 5);
            // Find exact name match with company type
            const companyMatch = searchResults.find(
              c => c.name.toLowerCase() === companyName.toLowerCase() && c.company_type === 'company'
            );
            if (companyMatch) {
              existingCompany = await companyApi.getCompanyById(companyMatch.id);
            }
          }
        }
      } catch (e) {
        // Company doesn't exist, which is what we want
      }

      if (existingCompany) {
        logger.info('Existing company found', {
          companyId: existingCompany.id,
          vat: existingCompany.vat,
          name: existingCompany.name,
          component: 'AdminFormsModal'
        });
        // Show option to link to existing company instead of error
        setFoundDuplicateCompany(existingCompany);
        updateStepStatus(0, 'success'); // Check passed - found existing
        return;
      }
      updateStepStatus(0, 'success');

      // Шаг 2-4: Создание компании с Telegram группой и чатом через Saga
      // Single API call triggers CompanyCreationSaga which handles:
      // - Creating Telegram supergroup
      // - Linking it to company
      // - Creating/linking company chat
      updateStepStatus(1, 'loading');
      logger.info('Creating company with saga orchestration via single API call');

      const companyData = {
        name: companyFormData.company_name || '',
        company_type: isProject ? 'project' : 'company',
        vat: isProject ? undefined : (companyFormData.vat || undefined),
        ogrn: isProject ? undefined : (companyFormData.ogrn || undefined),
        kpp: isProject ? undefined : (companyFormData.kpp || undefined),
        director: companyFormData.director || undefined,
        email: companyFormData.email || undefined,
        phone: companyFormData.phone || undefined,
        street: companyFormData.street || undefined,
        city: companyFormData.city || undefined,
        postal_code: companyFormData.postal_code || undefined,
        country_id: 190, // Russia by default
        // Saga orchestration options - triggers CompanyCreationSaga
        create_telegram_group: true,
        telegram_group_title: telegramGroupData.title || companyFormData.company_name,
        telegram_group_description: telegramGroupData.description || `Рабочая группа для ${companyFormData.company_name}`,
        // Auto-create company chat theme
        create_chat: true,
        // If we have an active chat, link it instead of creating new
        link_chat_id: activeChat?.id || undefined,
      };

      logger.debug('Prepared company data with saga options', {
        companyData,
        component: 'AdminFormsModal'
      });

      // Single API call - saga handles the rest asynchronously
      const createResponse = await companyApi.createCompany(companyData);
      const newCompany = { id: createResponse.id, ...companyData };

      logger.info('Company created, saga triggered', {
        companyId: newCompany.id,
        sagaTriggered: true
      });

      // OPTIMISTIC UI: Dispatch companyCreated event immediately for instant UI update
      // This adds the group to the sidebar before WSE event arrives from backend
      window.dispatchEvent(new CustomEvent('companyCreated', {
        detail: {
          company_id: createResponse.id,
          id: createResponse.id,
          name: companyData.name,
          company_name: companyData.name,
          company_type: companyData.company_type,
          description: companyData.telegram_group_description,
          created_at: new Date().toISOString(),
          logo_url: null,
        }
      }));

      // Note: Chat will be added when groupCreationCompleted WSE event arrives
      // This event contains the real chat_id from the saga

      logger.info('Dispatched companyCreated event for optimistic UI', {
        companyId: createResponse.id,
        companyName: companyData.name
      });

      // Mark all steps as successful since saga will handle them
      updateStepStatus(1, 'success');
      updateStepStatus(2, 'success');
      updateStepStatus(3, 'success');

      // Clear and reload cache if we had an active chat
      if (activeChat?.id) {
        clearCompanyCache(activeChat.id);
        await loadCompanyForChat(activeChat.id);
      }

      // Create result object for UI display
      // Note: Actual telegram group data will come from saga completion event via WSE
      setGroupCreationResult({
        success: true,
        telegram_group_id: null, // Will be updated when saga completes
        title: telegramGroupData.title || companyFormData.company_name,
        invite_link: null, // Will be updated when saga completes
        group_data: {
          group_title: telegramGroupData.title || companyFormData.company_name,
        }
      });
      setCreatedCompanyData(newCompany);

      logger.info('Company creation process initiated successfully', {
        companyId: newCompany.id,
        sagaOrchestrated: true
      });

      // Вызываем onSuccess если передан
      if (onSuccess) {
        onSuccess();
      }
    } catch (error: any) {
      logger.error('Unexpected error during company creation', error);
      const errorMessage = error?.response?.data?.detail
        || error?.message
        || 'Произошла неожиданная ошибка при создании компании';
      setProcessError(errorMessage);
      updateStepStatus(1, 'error');
    }
  };
  const handleSave = async () => {
    if (!user) {
      return;
    }
    const currentData = companyFormData;
    const validationErrors = validateCompanyForm(companyFormData);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    // Показываем процесс создания компании внутри модала
    const steps = ['Проверка дубликатов', 'Создание компании', 'Создание Telegram группы', 'Привязка чата'];
    setProcessSteps(steps);
    setStepStatuses(steps.map(() => 'pending'));
    setCurrentStep(0);
    setProcessError('');
    setShowingProcess(true);
    setTimeout(() => {
      startCompanyCreation();
    }, 100);
  };
  useEffect(() => {
    if (isOpen) {
      setIsEditing(true);
      setErrors({});
      setIsSearching(false);
      setIsProject(false);
      setGroupCreationResult(null);
      setCreatedCompanyData(null);
      setFoundDuplicateCompany(null);
      setShowingProcess(false);
      setProcessSteps([]);
      setCurrentStep(0);
      setStepStatuses([]);
      setProcessError('');
      setTelegramGroupData({
        title: '',
        description: 'Рабочая группа WellWon Logistics'
      });
      if (formType === 'company-registration') {
        setCompanyFormData({
          vat: '',
          kpp: '',
          ogrn: '',
          company_name: '',
          email: '',
          phone: '',
          street: '',
          city: '',
          postal_code: '',
          country: '',
          director: '',
          company_type: ''
        });

        // Update Telegram group title when company name changes
        setTelegramGroupData(prev => ({
          ...prev,
          title: ''
        }));
      }
    }
  }, [isOpen, formType]);
  const getFormTitle = () => {
    switch (formType) {
      case 'company-registration':
        return 'Регистрация компании';
      default:
        return 'Административная форма';
    }
  };
  const getFormIcon = () => {
    switch (formType) {
      case 'company-registration':
        return <Building className="h-5 w-5" />;
      default:
        return null;
    }
  };
  return <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-background border-glass-border">
        <DialogHeader className="flex flex-row items-center gap-3 space-y-0 pb-6 border-b border-glass-border">
          {getFormIcon()}
          <div className="flex-1">
            <DialogTitle className="text-xl text-text-white">{getFormTitle()}</DialogTitle>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-glass-surface rounded-lg transition-colors">
            <X className="h-4 w-4 text-text-gray-400" />
          </button>
        </DialogHeader>

        <div className="space-y-6">
          {isLoading && <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-accent-red" />
              <span className="ml-2 text-text-gray-400">Загрузка...</span>
            </div>}

          {showingProcess && <div className="w-full bg-glass-surface/30 border border-glass-border rounded-lg p-6">
              <div className="flex flex-col items-center space-y-6">
                {/* Заголовок */}
                <div className="text-center">
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    Создание компании
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Пожалуйста, подождите...
                  </p>
                </div>

                {/* Прогресс бар */}
                <div className="w-full">
                    <div className={`rounded-full h-2 mb-4 ${
                      stepStatuses.some(s => s === 'error') ? 'bg-accent-red/20' : 'bg-secondary'
                    }`}>
                     <div className={`h-2 rounded-full transition-all duration-500 ${
                       stepStatuses.some(s => s === 'error') ? 'bg-accent-red' : 'bg-accent-blue'
                     }`} style={{
                   width: `${stepStatuses.filter(s => s === 'success').length / processSteps.length * 100}%`
                 }} />
                  </div>
                </div>

                {/* Этапы - первая карточка */}
                <div className="w-full p-4 border border-border rounded-lg bg-card/50">
                  <div className="space-y-3">
                    {processSteps.map((step, index) => <div key={index} className="flex items-center space-x-3">
                        {/* Статус этапа */}
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${stepStatuses[index] === 'success' ? 'bg-accent-green text-white' : stepStatuses[index] === 'error' ? 'bg-accent-red text-white' : stepStatuses[index] === 'loading' ? 'bg-accent-blue text-white animate-pulse' : 'bg-secondary text-muted-foreground'}`}>
                          {stepStatuses[index] === 'success' ? '✓' : stepStatuses[index] === 'error' ? '✗' : stepStatuses[index] === 'loading' ? '...' : index + 1}
                        </div>
                        
                        {/* Название этапа */}
                        <span className={`text-sm ${stepStatuses[index] === 'success' ? 'text-accent-green' : stepStatuses[index] === 'error' ? 'text-accent-red' : stepStatuses[index] === 'loading' ? 'text-accent-blue' : 'text-muted-foreground'}`}>
                          {step}
                        </span>
                      </div>)}
                  </div>
                </div>

                {/* Результат процесса создания - вторая карточка */}
                {groupCreationResult && createdCompanyData && (
                  <div className="w-full p-4 border border-border rounded-lg bg-card/50 space-y-6">
                    <div className="text-center">
                      <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center rounded-full bg-accent-green/10">
                        <CheckCircle className="w-8 h-8 text-accent-green" />
                      </div>
                      <h4 className="text-lg font-semibold text-foreground mb-6">
                        Компания и группа успешно созданы!
                      </h4>
                      
                      {/* Divider */}
                      <div className="w-full h-px bg-border mb-6"></div>
                    </div>
                    
                    {/* Данные в красивых полях по 2 в строке */}
                    <div className="grid grid-cols-2 gap-4">
                      {/* Название компании */}
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Название компании</label>
                        <div className="px-3 py-2 bg-background border border-border rounded-md text-sm">
                          {createdCompanyData.name}
                        </div>
                      </div>
                      
                      {/* ID компании */}
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">ID компании</label>
                        <div className="px-3 py-2 bg-background border border-border rounded-md text-sm">
                          {createdCompanyData.id}
                        </div>
                      </div>
                      
                      {/* Название группы */}
                      {groupCreationResult?.group_data && (
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Название группы</label>
                          <div className="px-3 py-2 bg-background border border-border rounded-md text-sm">
                            {groupCreationResult.group_data.group_title || groupCreationResult.group_title}
                          </div>
                        </div>
                      )}
                      
                      {/* ID группы */}
                      {groupCreationResult?.group_data && (
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">ID группы</label>
                          <div className="px-3 py-2 bg-background border border-border rounded-md text-sm">
                            {groupCreationResult.group_data.group_id ? `-100${groupCreationResult.group_data.group_id}` : (groupCreationResult.group_id ? `-100${groupCreationResult.group_id}` : 'Не указан')}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Ссылка приглашения */}
                    {(groupCreationResult?.group_data?.invite_link || groupCreationResult?.invite_link) && (
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Ссылка приглашение в группу</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={groupCreationResult.group_data?.invite_link || groupCreationResult.invite_link}
                            readOnly
                            className="flex-1 px-3 py-2 bg-background border border-border rounded-md text-sm"
                          />
                          <GlassButton
                            variant="outline"
                            size="sm"
                            onClick={() => handleCopyClick(groupCreationResult.group_data?.invite_link || groupCreationResult.invite_link, 'invite-link')}
                            className="border-border hover:bg-white/5"
                          >
                            {copiedStates['invite-link'] ? (
                              <Check className="w-4 h-4 text-accent-green" />
                            ) : (
                              <Copy className="w-4 h-4 text-muted-foreground" />
                            )}
                          </GlassButton>
                        </div>
                      </div>
                    )}
                    
                    {/* Кнопки */}
                    <div className="flex gap-3 justify-center">
                      {(groupCreationResult?.group_data?.invite_link || groupCreationResult?.invite_link) && (
                        <GlassButton
                          variant="primary"
                          onClick={() => window.open(groupCreationResult.group_data?.invite_link || groupCreationResult.invite_link, '_blank')}
                          className="bg-[#0088cc] hover:bg-[#0088cc]/90 text-white"
                        >
                          <TelegramIcon className="w-4 h-4 mr-2" />
                          Открыть группу
                        </GlassButton>
                      )}
                      <GlassButton variant="secondary" onClick={handleProcessClose}>
                        Закрыть
                      </GlassButton>
                    </div>
                  </div>
                )}

                {/* Found duplicate company/project - offer to link */}
                {foundDuplicateCompany && !groupCreationResult && (
                  <div className="w-full p-4 border border-yellow-500/30 rounded-lg bg-card/50 space-y-6">
                    <div className="text-center">
                      <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center rounded-full bg-yellow-500/10">
                        <Building className="w-8 h-8 text-yellow-400" />
                      </div>
                      <h4 className="text-lg font-semibold text-foreground mb-2">
                        {foundDuplicateCompany.company_type === 'project'
                          ? 'Найден существующий проект'
                          : 'Найдена существующая компания'}
                      </h4>
                      <p className="text-sm text-muted-foreground mb-2">
                        {foundDuplicateCompany.company_type === 'project'
                          ? `Проект с таким названием уже существует в системе:`
                          : `Компания ${foundDuplicateCompany.vat ? `с ИНН (${foundDuplicateCompany.vat})` : 'с таким названием'} уже существует в системе:`
                        }
                      </p>
                      <p className="text-sm text-foreground font-medium mb-4">
                        {foundDuplicateCompany.name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {foundDuplicateCompany.company_type === 'project'
                          ? 'Хотите создать Telegram группу и привязать к существующему проекту?'
                          : 'Хотите создать Telegram группу и привязать к существующей компании?'
                        }
                      </p>
                    </div>
                    <div className="flex gap-3 justify-center">
                      <GlassButton
                        variant="primary"
                        onClick={handleLinkToExistingCompany}
                        className="bg-yellow-500/80 hover:bg-yellow-500/90 text-white"
                      >
                        <Building className="w-4 h-4 mr-2" />
                        {foundDuplicateCompany.company_type === 'project'
                          ? 'Привязать к проекту'
                          : 'Привязать к компании'
                        }
                      </GlassButton>
                      <GlassButton variant="secondary" onClick={handleCreateNewAnyway}>
                        Отмена
                      </GlassButton>
                    </div>
                  </div>
                )}

                {/* Ошибка */}
                {processError && !groupCreationResult && !foundDuplicateCompany && (
                  <div className="w-full p-4 border border-border rounded-lg bg-card/50 space-y-6">
                    <div className="text-center">
                      <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center rounded-full bg-accent-red/10">
                        <XCircle className="w-8 h-8 text-accent-red" />
                      </div>
                      <h4 className="text-lg font-semibold text-foreground mb-2">
                        Ошибка создания компании
                      </h4>
                      <p className="text-sm text-muted-foreground mb-6">
                        {processError}
                      </p>
                    </div>
                    <div className="flex justify-center">
                      <GlassButton variant="secondary" onClick={handleProcessClose}>
                        Закрыть
                      </GlassButton>
                    </div>
                  </div>
                )}
              </div>
            </div>}

          {!isLoading && !showingProcess && formType === 'company-registration' && <div className="space-y-6">
              {/* Блок 1: Информация о компании/проекте */}
              <GlassCard className="space-y-6" hover={false}>
                {/* Company/Project Toggle */}
                <div className="flex items-center space-x-3 p-4 bg-glass-surface rounded-xl border border-glass-border">
                  <Switch id="project-mode" checked={isProject} onCheckedChange={handleProjectToggle} />
                  <Label htmlFor="project-mode" className="text-text-white font-medium">
                    Нет компании
                  </Label>
                </div>

                <CompanyInfoFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} isProject={isProject} isSearching={isSearching} onSearchByINN={handleSearchByINN} getFieldIndicatorColor={getFieldIndicatorColor} />
                
                <AddressFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} isProject={isProject} getFieldIndicatorColor={getFieldIndicatorColor} />
                
                <ContactInfoFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} getFieldIndicatorColor={getFieldIndicatorColor} />
              </GlassCard>

              {/* Блок 2: Создание Telegram-группы */}
              <GlassCard variant="default" padding="lg" className="border-white/10" hover={false}>
                <div className="space-y-6">
                  <h3 className="text-text-white font-semibold text-xl mb-6 flex items-center gap-3">
                    <TelegramIcon className="w-6 h-6 text-[#0088cc]" />
                    Создание Telegram-группы
                  </h3>
                  
                  <TelegramGroupFields groupData={telegramGroupData} setGroupData={setTelegramGroupData} />
                </div>
              </GlassCard>
              
              {/* Кнопки действий */}
              <FormActions isEditing={isEditing} isSaving={isLoading} hasChanges={true} onCancel={handleCancel} onSave={handleSave} isProject={isProject} isCreatingGroup={false} />
            </div>}


          {!isLoading && !formType && <div className="text-center py-8">
              <Building size={48} className="text-text-gray-400 mx-auto mb-4" />
              <h3 className="text-text-white font-medium mb-2">Выберите тип формы</h3>
              <p className="text-text-gray-400 text-sm">Выберите нужную форму из меню</p>
            </div>}
        </div>
      </DialogContent>
    </Dialog>;
};