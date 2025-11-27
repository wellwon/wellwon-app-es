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
import { supabase } from '@/integrations/supabase/client';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { FormSection } from '@/components/design-system/FormSection';
import { GlassCard, GlassButton } from '@/components/design-system';
import { CompanyService } from '@/services/CompanyService';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { usePlatform } from '@/contexts/PlatformContext';
import { logger } from '@/utils/logger';

// Константа URL логотипа для Telegram групп
const TELEGRAM_GROUP_LOGO_URL = 'https://qqhuwvveovmfyihjnanx.supabase.co/storage/v1/object/sign/App%20Files/Group%20Logo.png?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8zZmYxMTc1NS1iNWJhLTRlMzEtODBlYS1lMDFjZTU4ZTAyNTQiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJBcHAgRmlsZXMvR3JvdXAgTG9nby5wbmciLCJpYXQiOjE3NTUxNzkzNTQsImV4cCI6NDg3NzI0MzM1NH0.RXCeye2yyXWu7ZLPYAosPh0v5kCjphelOHU4Aygbgxg';

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
  const { isLightTheme } = usePlatform();

  // Theme object for form styling per DESIGN_SYSTEM.md §19
  const theme = isLightTheme ? {
    modal: { bg: 'bg-[#f4f4f4]', border: 'border-gray-300' },
    card: { bg: 'bg-white', border: 'border-gray-300', shadow: 'shadow-sm' },
    toggle: { bg: 'bg-gray-50', border: 'border-gray-300' },
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-500' },
    closeButton: 'hover:bg-gray-100 text-gray-500'
  } : {
    modal: { bg: 'bg-[#1a1a1e]', border: 'border-white/10' },
    card: { bg: 'bg-[#232328]', border: 'border-white/10', shadow: '' },
    toggle: { bg: 'bg-[#1e1e22]', border: 'border-white/10' },
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    closeButton: 'hover:bg-white/10 text-gray-400'
  };
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
      const {
        data,
        error
      } = await supabase.functions.invoke('dadata-api-inn', {
        body: {
          vat: vatValue
        }
      });
        if (error) {
          return;
        }
      if (!data.suggestions || data.suggestions.length === 0) {
        setErrors(prev => ({
          ...prev,
          vat: 'Компания с таким ИНН не найдена'
        }));
        return;
      }

      // Обработка успешного ответа
      const company = data.suggestions[0].data;

      // Извлечение адреса (убираем все до "ул" включительно)
      let street = company.address?.value || '';
      const streetIndex = street.toLowerCase().indexOf('ул');
      if (streetIndex !== -1) {
        street = street.substring(streetIndex);
      }

      // Страна по умолчанию
      const countryName = company.address?.data?.country || '';

      // Директор - может быть в разных местах
      let directorName = '';
      if (company.management && company.management.name) {
        directorName = company.management.name;
      } else if (company.managers && company.managers.length > 0) {
        directorName = company.managers[0].name;
      }

      // Обновляем форму найденными данными
      const newFormData = {
        ...companyFormData,
        company_name: company.name?.short_with_opf || companyFormData.company_name,
        name: company.name?.short_with_opf || companyFormData.company_name,
        ogrn: company.ogrn || companyFormData.ogrn,
        kpp: company.kpp || companyFormData.kpp,
        email: company.emails?.[0] || companyFormData.email,
        city: company.address?.data?.city || companyFormData.city,
        postal_code: company.address?.data?.postal_code || companyFormData.postal_code,
        street: street,
        country: countryName,
        director: directorName
      };

      // Обновляем поле ИНН
      newFormData.vat = vatValue;
      setCompanyFormData(newFormData);

      // Update Telegram group title when company name is loaded
      setTelegramGroupData(prevGroup => ({
        ...prevGroup,
        title: newFormData.company_name || prevGroup.title
      }));
    } catch (error) {
      // Error handled by showing in form validation
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

      // Проверяем дубликаты используя CompanyService
      const vatValue = companyFormData.vat;
      const companyName = companyFormData.company_name;
      
      logger.debug('Checking for duplicate company', {
        vat: vatValue,
        name: companyName,
        isProject,
        component: 'AdminFormsModal'
      });
      
      const isDuplicate = await CompanyService.checkCompanyExists(
        isProject ? undefined : vatValue, // Для проектов не проверяем ИНН
        companyName
      );
      
      if (isDuplicate) {
        logger.warn('Company already exists', {
          vat: vatValue,
          name: companyName,
          isProject,
          component: 'AdminFormsModal'
        });
        updateStepStatus(0, 'error');
        
        if (isProject) {
          setProcessError(`Проект с таким названием уже существует: "${companyName}"`);
        } else {
          setProcessError(`Компания ${vatValue ? `с ИНН ${vatValue}` : `с названием "${companyName}"`} уже существует`);
        }
        return;
      }
      updateStepStatus(0, 'success');

      // Шаг 2: Создание компании
      updateStepStatus(1, 'loading');
      logger.info('Creating company via CompanyService');
      
      // Логируем данные формы перед созданием компании
      logger.debug('Form data before company creation', {
        formData: companyFormData,
        isProject,
        component: 'AdminFormsModal'
      });
      
      const companyData = {
        name: companyFormData.company_name || '',
        company_type: isProject ? 'project' : 'company',
        vat: isProject ? null : (companyFormData.vat || null),
        ogrn: isProject ? null : (companyFormData.ogrn || null),
        kpp: isProject ? null : (companyFormData.kpp || null),
        director: companyFormData.director || null,
        email: companyFormData.email || null,
        phone: companyFormData.phone || null,
        street: companyFormData.street || null,
        city: companyFormData.city || null,
        postal_code: companyFormData.postal_code || null,
        country: companyFormData.country || null
      };
      
      // Логируем подготовленные данные для создания компании
      logger.debug('Prepared company data for creation', {
        companyData,
        component: 'AdminFormsModal'
      });
      const newCompany = await CompanyService.createCompany(companyData, user!.id, user!.id);
      updateStepStatus(1, 'success');

      // Шаг 3: Создание Telegram группы
      updateStepStatus(2, 'loading');
      logger.info('Creating Telegram group', {
        companyId: newCompany.id,
        photoUrl: TELEGRAM_GROUP_LOGO_URL
      });
      const telegramResponse = await supabase.functions.invoke('telegram-group-create', {
        body: {
          title: telegramGroupData.title || `${companyFormData.company_name} - Группа`,
          description: telegramGroupData.description || `Рабочая группа для ${companyFormData.company_name}`,
          photo_url: TELEGRAM_GROUP_LOGO_URL,
          company_id: newCompany.id
        }
      });
      if (telegramResponse.error) {
        logger.error('Failed to create Telegram group', telegramResponse.error);
        updateStepStatus(2, 'error');
        setProcessError('Не удалось создать Telegram группу');
        return;
      }
      
      const telegramData = telegramResponse.data;
      
      // Check if the response indicates failure
      if (!telegramData || !telegramData.success) {
        const errorMessage = telegramData?.error || 'Неизвестная ошибка при создании Telegram группы';
        logger.error('Telegram group creation failed', { error: errorMessage, response: telegramData });
        updateStepStatus(2, 'error');
        setProcessError(errorMessage);
        return;
      }
      
      logger.info('Telegram group created successfully', {
        ...telegramData,
        photoSet: telegramData.group_data?.photo_set,
        existing: telegramData.group_data?.existing
      });
      updateStepStatus(2, 'success');

      // Шаг 4: Привязка чата с компанией
      updateStepStatus(3, 'loading');
      if (activeChat?.id) {
        logger.info('Linking chat to company', {
          chatId: activeChat.id,
          companyId: newCompany.id
        });

        // Связываем чат с компанией через обновление чата
        const {
          error: linkError
        } = await supabase.from('chats').update({
          company_id: newCompany.id
        }).eq('id', activeChat.id);
        if (linkError) {
          logger.error('Failed to link chat to company', linkError);
          updateStepStatus(3, 'error');
          setProcessError('Не удалось связать чат с компанией');
          return;
        }

        // Очищаем кеш компании для чата
        clearCompanyCache(activeChat.id);

        // Перезагружаем данные компании для чата
        await loadCompanyForChat(activeChat.id);
      }
      updateStepStatus(3, 'success');

      // Сохраняем результат для отображения в модале
      setGroupCreationResult(telegramData);
      setCreatedCompanyData(newCompany);

      logger.info('Company creation process completed successfully', {
        companyId: newCompany.id,
        telegramGroupId: telegramData.group_data?.id
      });

      // Вызываем onSuccess если передан
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      logger.error('Unexpected error during company creation', error);
      setProcessError('Произошла неожиданная ошибка при создании компании');
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
      <DialogContent className={`max-w-2xl max-h-[90vh] overflow-y-auto ${theme.modal.bg} border ${theme.modal.border}`}>
        <DialogHeader className="flex flex-row items-center gap-3 space-y-0">
          <span className="text-accent-red">{getFormIcon()}</span>
          <div className="flex-1">
            <DialogTitle className={`text-xl ${theme.text.primary}`}>{getFormTitle()}</DialogTitle>
          </div>
          <button onClick={onClose} className={`p-2 rounded-lg transition-colors ${theme.closeButton}`}>
            <X className="h-4 w-4" />
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

                {/* Ошибка */}
                {processError && !groupCreationResult && (
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
              <div className={`p-6 rounded-2xl ${theme.card.bg} border ${theme.card.border} ${theme.card.shadow} space-y-6`}>
                {/* Company/Project Toggle */}
                <div className={`flex items-center space-x-3 p-4 rounded-xl border ${theme.toggle.bg} ${theme.toggle.border}`}>
                  <Switch id="project-mode" checked={isProject} onCheckedChange={handleProjectToggle} />
                  <Label htmlFor="project-mode" className={`font-medium ${theme.text.primary}`}>
                    Нет компании
                  </Label>
                </div>

                <CompanyInfoFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} isProject={isProject} isSearching={isSearching} onSearchByINN={handleSearchByINN} getFieldIndicatorColor={getFieldIndicatorColor} isLightTheme={isLightTheme} />

                <AddressFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} isProject={isProject} getFieldIndicatorColor={getFieldIndicatorColor} isLightTheme={isLightTheme} />

                <ContactInfoFields formData={companyFormData} setFormData={setCompanyFormData} errors={errors} isEditing={isEditing} getFieldIndicatorColor={getFieldIndicatorColor} isLightTheme={isLightTheme} />
              </div>

              {/* Блок 2: Создание Telegram-группы */}
              <div className={`p-6 rounded-2xl ${theme.card.bg} border ${theme.card.border} ${theme.card.shadow}`}>
                <div className="space-y-6">
                  <h3 className={`font-semibold text-xl mb-6 flex items-center gap-3 ${theme.text.primary}`}>
                    <TelegramIcon className="w-6 h-6 text-[#0088cc]" />
                    Создание Telegram-группы
                  </h3>

                  <TelegramGroupFields groupData={telegramGroupData} setGroupData={setTelegramGroupData} isLightTheme={isLightTheme} />
                </div>
              </div>

              {/* Кнопки действий */}
              <FormActions isEditing={isEditing} isSaving={isLoading} hasChanges={true} onCancel={handleCancel} onSave={handleSave} isProject={isProject} isCreatingGroup={false} isLightTheme={isLightTheme} />
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