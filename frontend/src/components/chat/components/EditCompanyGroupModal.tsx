import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Loader2, Building, Edit3, Copy, X, XCircle } from 'lucide-react';
import AppConfirmDialog from '@/components/shared/AppConfirmDialog';
import { CompanyFormData, SupergroupFormData, FormValidationErrors } from '@/types/company-form';
import { CompanyInfoFields } from './forms/CompanyInfoFields';
import { AddressFields } from './forms/AddressFields';
import { ContactInfoFields } from './forms/ContactInfoFields';
import { GlassInput } from '@/components/design-system/GlassInput';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import * as companyApi from '@/api/company';
import * as telegramApi from '@/api/telegram';
import { CompanyLogoUploader } from './CompanyLogoUploader';
import { toast } from '@/hooks/use-toast';
import { logger } from '@/utils/logger';
import { useAuth } from '@/contexts/AuthContext';
import { API } from '@/api/core';

interface EditCompanyGroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  supergroupId: number;
  companyId?: number;
  onSuccess?: () => void;
  initialCompanyType?: string;
  preloadedCompanyData?: CompanyFormData;
  preloadedSupergroupData?: SupergroupFormData;
}

export const EditCompanyGroupModal: React.FC<EditCompanyGroupModalProps> = ({
  isOpen,
  onClose,
  supergroupId,
  companyId,
  onSuccess,
  initialCompanyType,
  preloadedCompanyData,
  preloadedSupergroupData
}) => {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(!preloadedCompanyData || !preloadedSupergroupData);
  const [isEditing, setIsEditing] = useState(true);
  const [errors, setErrors] = useState<FormValidationErrors>({});
  const [isSaving, setIsSaving] = useState(false);
  const [isProject, setIsProject] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [showDuplicateDialog, setShowDuplicateDialog] = useState(false);
  const [duplicateCompanyData, setDuplicateCompanyData] = useState<any>(null);
  const [companyFormData, setCompanyFormData] = useState<CompanyFormData>(
    preloadedCompanyData || {
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
    }
  );
  const [supergroupFormData, setSupergroupFormData] = useState<SupergroupFormData>(
    preloadedSupergroupData || {
      title: '',
      description: '',
      username: '',
      invite_link: '',
      member_count: 0,
      is_forum: false,
      company_logo: '',
      group_type: 'others'
    }
  );

  // Состояние для диалога подтверждения
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [existingCompanyData, setExistingCompanyData] = useState<any>(null);

  // Состояние для отслеживания изменений
  const [originalCompanyData, setOriginalCompanyData] = useState<CompanyFormData | null>(null);
  const [originalSupergroupData, setOriginalSupergroupData] = useState<SupergroupFormData | null>(null);
  const [originalIsProject, setOriginalIsProject] = useState<boolean>(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Загрузка данных при открытии модала (только если данные не предзагружены)
  useEffect(() => {
    if (isOpen && supergroupId && companyId && (!preloadedCompanyData || !preloadedSupergroupData)) {
      loadData();
    }
    // Если данные предзагружены, но у супергруппы нет логотипа или group_type, попробуем их загрузить отдельно
    else if (isOpen && preloadedSupergroupData && (!preloadedSupergroupData.company_logo || !preloadedSupergroupData.group_type) && supergroupId) {
      fetchMissingData();
    }
    // Также загружаем данные если companyId не предоставлен (например, при создании новой компании)
    else if (isOpen && supergroupId && !companyId && !preloadedSupergroupData) {
      loadData();
    }
  }, [isOpen, supergroupId, companyId, preloadedCompanyData, preloadedSupergroupData]);

  // Инициализация исходных данных - после загрузки данных
  useEffect(() => {
    if (isOpen) {
      if (preloadedCompanyData && preloadedSupergroupData) {
        // Сначала устанавливаем состояние тумблера
        const projectState = preloadedCompanyData.company_type === 'project';
        setIsProject(projectState);
        
        // Устанавливаем данные форм из предзагруженных данных
        setCompanyFormData(preloadedCompanyData);
        setSupergroupFormData(preloadedSupergroupData);
        
        // Инициализация с предзагруженными данными
        setTimeout(() => {
          setOriginalCompanyData(preloadedCompanyData);
          setOriginalSupergroupData(preloadedSupergroupData);
          setOriginalIsProject(projectState);
          setIsInitialized(true);
          setHasChanges(false);
          logger.info('Initialized with preloaded data', { 
            preloadedCompanyData, 
            preloadedSupergroupData,
            projectState,
            component: 'EditCompanyGroupModal' 
          });
        }, 100);
      }
    } else {
      // Reset when modal closes
      setIsInitialized(false);
      setHasChanges(false);
      setOriginalCompanyData(null);
      setOriginalSupergroupData(null);
    }
  }, [isOpen, preloadedCompanyData, preloadedSupergroupData]);

  // Отслеживание изменений - только после инициализации
  useEffect(() => {
    if (!isInitialized || !originalCompanyData || !originalSupergroupData) return;

    const companyChanged = JSON.stringify(companyFormData) !== JSON.stringify(originalCompanyData);
    const supergroupChanged = JSON.stringify(supergroupFormData) !== JSON.stringify(originalSupergroupData);
    const projectChanged = isProject !== originalIsProject;

    const hasAnyChanges = companyChanged || supergroupChanged || projectChanged;
    
    logger.info('Change tracking', {
      companyChanged,
      supergroupChanged,
      projectChanged,
      hasAnyChanges,
      isInitialized,
      component: 'EditCompanyGroupModal'
    });

    setHasChanges(hasAnyChanges);
  }, [companyFormData, supergroupFormData, isProject, originalCompanyData, originalSupergroupData, originalIsProject, isInitialized]);

  const fetchMissingData = async () => {
    try {
      const supergroupData = await telegramApi.getGroupInfo(supergroupId);
      if (supergroupData) {
        setSupergroupFormData(prev => ({
          ...prev,
          company_logo: supergroupData.company_logo || prev.company_logo || '',
          group_type: supergroupData.group_type || prev.group_type || 'others'
        }));
        logger.info('Fetched missing data for supergroup', { 
          supergroupId, 
          logo: supergroupData.company_logo,
          group_type: supergroupData.group_type,
          component: 'EditCompanyGroupModal' 
        });
      }
    } catch (error) {
      logger.warn('Failed to fetch missing data', { error, supergroupId, component: 'EditCompanyGroupModal' });
    }
  };

  const loadData = async () => {
    setIsLoading(true);
    try {
      // Загружаем данные компании и супергруппы параллельно
      const [companyData, supergroupData] = await Promise.all([
        companyApi.getCompanyById(companyId as number),
        telegramApi.getGroupInfo(supergroupId)
      ]);
      
      if (companyData) {
        const loadedCompanyData = {
          id: companyData.id,
          vat: companyData.vat || '',
          kpp: companyData.kpp || '',
          ogrn: companyData.ogrn || '',
          company_name: companyData.name || '',
          email: companyData.email || '',
          phone: companyData.phone || '',
          street: companyData.street || '',
          city: companyData.city || '',
          postal_code: companyData.postal_code || '',
          country: companyData.country || '',
          director: companyData.director || '',
          company_type: companyData.company_type || '',
          logo_url: companyData.logo_url || ''
        };
        
        setCompanyFormData(loadedCompanyData);
        setOriginalCompanyData(loadedCompanyData);
        logger.info('Set original company data', { loadedCompanyData, component: 'EditCompanyGroupModal' });

        // Устанавливаем состояние тумблера на основе типа компании
        const projectState = companyData.company_type === 'project';
        setIsProject(projectState);
        setOriginalIsProject(projectState);
      }
      
      if (supergroupData) {
        logger.info('Loading supergroup data', { supergroupData, component: 'EditCompanyGroupModal' });
        const loadedSupergroupData = {
          id: supergroupData.id,
          title: supergroupData.title || '',
          description: supergroupData.description || '',
          username: supergroupData.username || '',
          invite_link: supergroupData.invite_link || '',
          member_count: supergroupData.member_count || 0,
          is_forum: supergroupData.is_forum || false,
          company_id: supergroupData.company_id,
          company_logo: supergroupData.company_logo || '',
          group_type: supergroupData.group_type || 'others'
        };
        
        setSupergroupFormData(loadedSupergroupData);
        setOriginalSupergroupData(loadedSupergroupData);
        logger.info('Set original supergroup data', { loadedSupergroupData, component: 'EditCompanyGroupModal' });
        
        // Устанавливаем инициализацию после загрузки всех данных
        setTimeout(() => {
          setIsInitialized(true);
          setHasChanges(false);
        }, 100);
      } else {
        logger.warn('No supergroup data received', { supergroupId, component: 'EditCompanyGroupModal' });
      }
    } catch (error) {
      logger.error('Failed to load edit data', error, {
        component: 'EditCompanyGroupModal'
      });
      toast({
        title: "Ошибка загрузки",
        description: "Не удалось загрузить данные для редактирования",
        variant: "error"
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Валидация форм
  const validateCompanyForm = (data: CompanyFormData): FormValidationErrors => {
    const newErrors: FormValidationErrors = {};
    const isProject = data.company_type === 'project';
    if (!isProject) {
      if (!data.vat || data.vat.length < 10) {
        newErrors.vat = 'ИНН должен содержать минимум 10 символов';
      }
    }
    if (!data.company_name || data.company_name.length < 2) {
      newErrors.company_name = isProject ? 'Название проекта обязательно' : 'Название компании обязательно';
    }
    if (!data.street || data.street.length < 2) {
      newErrors.street = 'Адрес должен содержать минимум 2 символа';
    }
    if (!data.city || data.city.length < 2) {
      newErrors.city = 'Город должен содержать минимум 2 символа';
    }
    return newErrors;
  };
  const validateSupergroupForm = (data: SupergroupFormData): FormValidationErrors => {
    const newErrors: FormValidationErrors = {};
    if (!data.title || data.title.length < 2) {
      newErrors.title = 'Название группы должно содержать минимум 2 символа';
    }
    if (!data.description || data.description.length < 5) {
      newErrors.description = 'Описание должно содержать минимум 5 символов';
    }
    if (!data.group_type) {
      newErrors.group_type = 'Тип группы обязателен для выбора';
    }
    return newErrors;
  };

  // Цветовые индикаторы для полей
  const getFieldIndicatorColor = (fieldName: string): string => {
    if (errors[fieldName]) return 'border-l-destructive';
    return 'border-l-accent-red/30';
  };

  // Обработчик переключения тумблера
  const handleProjectToggle = (checked: boolean) => {
    setIsProject(checked);
    if (checked) {
      // При переключении в режим "проект" очищаем поля ИНН, КПП, ОГРН
      setCompanyFormData(prev => ({
        ...prev,
        vat: '',
        kpp: '',
        ogrn: '',
        company_type: 'project'
      }));
    } else {
      // При переключении в режим "компания"
      setCompanyFormData(prev => ({
        ...prev,
        company_type: 'company'
      }));
    }
  };

  // Функция поиска по ИНН через API
  const handleSearchByINN = async () => {
    if (!companyFormData.vat) {
      toast({
        title: "Ошибка",
        description: "Введите ИНН для поиска",
        variant: "error"
      });
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
      toast({
        title: "Ошибка валидации",
        description: "ИНН должен содержать от 10 до 12 цифр",
        variant: "error"
      });
      return;
    }
    
    setIsSearching(true);
    setErrors(prev => ({
      ...prev,
      vat: ''
    }));
    
    try {
      // Call DaData API via backend
      const { data: response } = await API.post('/companies/lookup-vat', { vat: vatValue });
      const data = response;

      if (!data) {
        toast({
          title: "Ошибка поиска",
          description: "Не удалось выполнить поиск по ИНН. Попробуйте позже.",
          variant: "error"
        });
        return;
      }
      
      if (!data.suggestions || data.suggestions.length === 0) {
        setErrors(prev => ({
          ...prev,
          vat: 'Компания с таким ИНН не найдена'
        }));
        toast({
          title: "Компания не найдена",
          description: "По указанному ИНН компания не найдена в базе данных",
          variant: "error"
        });
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
        ogrn: company.ogrn || companyFormData.ogrn,
        kpp: company.kpp || companyFormData.kpp,
        email: company.emails?.[0] || companyFormData.email,
        city: company.address?.data?.city || companyFormData.city,
        postal_code: company.address?.data?.postal_code || companyFormData.postal_code,
        country: company.address?.data?.country || companyFormData.country,
        street: street,
        director: directorName
      };

      // Обновляем поле ИНН
      newFormData.vat = vatValue;
      setCompanyFormData(newFormData);

      // Обновляем название Telegram группы
      setSupergroupFormData(prevGroup => ({
        ...prevGroup,
        title: newFormData.company_name || prevGroup.title
      }));
      
      toast({
        title: "Данные найдены",
        description: "Информация о компании успешно загружена",
        variant: "success"
      });
    } catch (error) {
      toast({
        title: "Ошибка",
        description: "Произошла ошибка при поиске данных",
        variant: "error"
      });
    } finally {
      setIsSearching(false);
    }
  };

  const copyInviteLink = async () => {
    if (!supergroupFormData.invite_link) return;
    try {
      await navigator.clipboard.writeText(supergroupFormData.invite_link);
      toast({
        title: "Ссылка скопирована",
        description: "Ссылка приглашения скопирована в буфер обмена",
        variant: "success"
      });
    } catch (error) {
      toast({
        title: "Ошибка копирования",
        description: "Не удалось скопировать ссылку",
        variant: "error"
      });
    }
  };

  const handleCancel = () => {
    onClose();
  };

  const handleSave = async () => {
    const companyErrors = validateCompanyForm(companyFormData);
    const supergroupErrors = validateSupergroupForm(supergroupFormData);
    const allErrors = {
      ...companyErrors,
      ...supergroupErrors
    };
    
    if (Object.keys(allErrors).length > 0) {
      setErrors(allErrors);
      return;
    }
    
    setIsSaving(true);
    try {
      let finalCompanyId = companyId;
      
      // Если компании нет (companyId === 0 или undefined), создаем новую
      if (!companyId) {
        // Проверяем текущего пользователя
        if (!user) {
          logger.error('Authentication error in company creation', null, { component: 'EditCompanyGroupModal' });
          throw new Error('Необходимо войти в систему для создания компании');
        }

        // Проверяем существование компании
        let existingCompany = null;
        try {
          if (companyFormData.vat) {
            existingCompany = await companyApi.getCompanyByVat(companyFormData.vat);
          }
          if (!existingCompany && companyFormData.company_name) {
            const searchResults = await companyApi.searchCompanies(companyFormData.company_name, 1);
            if (searchResults.length > 0 && searchResults[0].name === companyFormData.company_name) {
              existingCompany = searchResults[0];
            }
          }
        } catch (e) {
          // Company doesn't exist, which is what we want
        }

        if (existingCompany) {
          setDuplicateCompanyData(existingCompany);
          setShowDuplicateDialog(true);
          return;
        } else {
          // Создаем новую компанию
          const newCompany = await companyApi.createCompany({
            name: companyFormData.company_name,
            company_type: isProject ? 'project' : 'company',
            vat: isProject ? null : companyFormData.vat,
            kpp: isProject ? null : companyFormData.kpp,
            ogrn: isProject ? null : companyFormData.ogrn,
            director: companyFormData.director,
            email: companyFormData.email,
            phone: companyFormData.phone,
            street: isProject ? null : companyFormData.street,
            city: isProject ? null : companyFormData.city,
            postal_code: isProject ? null : companyFormData.postal_code,
            country: companyFormData.country,
            logo_url: companyFormData.logo_url
          }, user.id);
          
          finalCompanyId = newCompany.id;
        }
      } else {
        // Обновляем существующую компанию
        const companyUpdates = {
          name: companyFormData.company_name,
          vat: companyFormData.vat,
          kpp: companyFormData.kpp,
          ogrn: companyFormData.ogrn,
          director: companyFormData.director,
          email: companyFormData.email,
          phone: companyFormData.phone,
          street: companyFormData.street,
          city: companyFormData.city,
          postal_code: companyFormData.postal_code,
          country: companyFormData.country,
          company_type: isProject ? 'project' : 'company',
          logo_url: companyFormData.logo_url
        };
        await companyApi.updateCompany(companyId, companyUpdates);
      }
      
      // Обновляем супергруппу одним вызовом с company_id
      const supergroupUpdates: any = {
        title: supergroupFormData.title,
        description: supergroupFormData.description,
        company_logo: supergroupFormData.company_logo,
        company_id: finalCompanyId // Include company_id in the single update
      };
      
      // Добавляем group_type только если он определен
      if (supergroupFormData.group_type) {
        supergroupUpdates.group_type = supergroupFormData.group_type;
      }
      
      const updatedSupergroup = await telegramApi.updateSupergroup(supergroupId, supergroupUpdates);
      // Обновляем исходные данные после успешного сохранения
      setOriginalCompanyData({ ...companyFormData });
      setOriginalSupergroupData({ ...supergroupFormData });
      setOriginalIsProject(isProject);
      setHasChanges(false);

      // Вызываем onSuccess для обновления списка групп
      onSuccess?.();
    } catch (error) {
      // Improved error logging with more details
      logger.error('Failed to save changes', error, {
        component: 'EditCompanyGroupModal',
        companyFormData,
        supergroupFormData,
        errorMessage: (error as any)?.message,
        errorDetails: (error as any)?.details,
        errorHint: (error as any)?.hint
      });
      
      // Специальная обработка ошибки COMPANY_EXISTS
      if (error && typeof error === 'object' && 'message' in error) {
        const errorMessage = error.message as string;
        if (errorMessage.includes('COMPANY_EXISTS')) {
          toast({
            title: "Компания уже существует",
            description: "Компания с таким ИНН или названием уже зарегистрирована в системе",
            variant: "error"
          });
        } else {
          toast({
            title: "Ошибка сохранения",
            description: errorMessage || "Не удалось сохранить изменения",
            variant: "error"
          });
        }
      } else {
        toast({
          title: "Ошибка сохранения",
          description: "Не удалось сохранить изменения",
          variant: "error"
        });
      }
    } finally {
      setIsSaving(false);
    }
  };

  // Обработчик подтверждения привязки существующей компании
  const handleConfirmLinkExisting = async () => {
    if (!existingCompanyData) return;
    
    setShowConfirmDialog(false);
    setIsSaving(true);
    
    try {
      // Привязываем супергруппу к существующей компании
      await telegramApi.updateSupergroup(supergroupId, {
        company_id: existingCompanyData.id
      });
      
      // Обновляем данные супергруппы
      const supergroupUpdates: any = {
        title: supergroupFormData.title,
        description: supergroupFormData.description,
        username: supergroupFormData.username,
        invite_link: supergroupFormData.invite_link
      };
      
      // Добавляем group_type только если он определен
      if (supergroupFormData.group_type) {
        supergroupUpdates.group_type = supergroupFormData.group_type;
      }
      await telegramApi.updateSupergroup(supergroupId, supergroupUpdates);
      
      toast({
        title: "Успешно",
        description: "Компания привязана к группе",
        variant: "success"
      });
      
      if (onSuccess) {
        onSuccess();
      }
      onClose();
    } catch (error) {
      logger.error('Error linking existing company', error, { component: 'EditCompanyGroupModal' });
      toast({
        title: "Ошибка",
        description: "Не удалось привязать компанию к группе",
        variant: "error"
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Обработчик отмены привязки (создание новой компании)
  const handleCancelLinkExisting = async () => {
    setShowConfirmDialog(false);
    setIsSaving(true);

    try {
      // Проверяем текущего пользователя
      if (!user) {
        throw new Error('Необходимо войти в систему для создания компании');
      }

      // Создаем новую компанию принудительно
      const newCompany = await companyApi.createCompany({
        name: companyFormData.company_name,
        company_type: isProject ? 'project' : 'company',
        vat: isProject ? null : companyFormData.vat,
        kpp: isProject ? null : companyFormData.kpp,
        ogrn: isProject ? null : companyFormData.ogrn,
        director: companyFormData.director,
        email: companyFormData.email,
        phone: companyFormData.phone,
        street: isProject ? null : companyFormData.street,
        city: isProject ? null : companyFormData.city,
        postal_code: isProject ? null : companyFormData.postal_code
      });
      
      // Привязываем супергруппу к новой компании
      await telegramApi.updateSupergroup(supergroupId, {
        company_id: newCompany.id
      });
      
      // Обновляем данные супергруппы
      const supergroupUpdates: any = {
        title: supergroupFormData.title,
        description: supergroupFormData.description,
        username: supergroupFormData.username,
        invite_link: supergroupFormData.invite_link
      };
      
      // Добавляем group_type только если он определен
      if (supergroupFormData.group_type) {
        supergroupUpdates.group_type = supergroupFormData.group_type;
      }
      await telegramApi.updateSupergroup(supergroupId, supergroupUpdates);
      
      toast({
        title: "Успешно",
        description: "Новая компания создана и привязана к группе",
        variant: "success"
      });
      
      if (onSuccess) {
        onSuccess();
      }
      onClose();
    } catch (error) {
      logger.error('Error creating new company after cancel', error, { component: 'EditCompanyGroupModal' });
      toast({
        title: "Ошибка",
        description: "Не удалось создать новую компанию",
        variant: "error"
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-background border-glass-border">
        <DialogHeader className="flex flex-row items-center gap-3 space-y-0 pb-6 border-b border-glass-border">
          
          <div className="flex-1">
            <DialogTitle className="text-xl text-text-white">Редактирование компании и группы</DialogTitle>
            <DialogDescription className="sr-only">
              Модальное окно для редактирования информации о компании и Telegram-группе
            </DialogDescription>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-glass-surface rounded-lg transition-colors">
            <X className="h-4 w-4 text-text-gray-400" />
          </button>
        </DialogHeader>

        <div className="space-y-6">
          <GlassCard className="space-y-6" hover={false}>
            {/* Company/Project Toggle WITHOUT Logo */}
            <div className="flex items-center justify-between p-4 bg-glass-surface rounded-xl border border-glass-border">
              <div className="flex items-center space-x-3">
                <Switch id="project-mode" checked={isProject} onCheckedChange={handleProjectToggle} />
                <Label htmlFor="project-mode" className="text-text-white font-medium">
                  Нет компании
                </Label>
              </div>
              
              {/* Group Type Select */}
              <div className="flex items-center space-x-3">
                <Label className="text-text-white text-sm whitespace-nowrap">
                  Тип отношений
                </Label>
                <Select
                  value={supergroupFormData.group_type || ''}
                  onValueChange={(value) => setSupergroupFormData(prev => ({
                    ...prev,
                    group_type: value as 'client' | 'payments' | 'logistics' | 'buyers' | 'others' | 'wellwon'
                  }))}
                  disabled={!isEditing}
                >
                  <SelectTrigger className={`w-[160px] ${errors.group_type ? 'border-destructive' : ''}`}>
                    <SelectValue placeholder="Выберите тип" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-glass-border z-[200] pointer-events-auto">
                    <SelectItem value="client">Клиент</SelectItem>
                    <SelectItem value="payments">Платежи</SelectItem>
                    <SelectItem value="logistics">Логисты</SelectItem>
                    <SelectItem value="buyers">Закупщики</SelectItem>
                    <SelectItem value="others">Другие</SelectItem>
                    <SelectItem value="wellwon">WellWon</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <CompanyInfoFields 
              formData={companyFormData} 
              setFormData={setCompanyFormData} 
              errors={errors} 
              isEditing={isEditing} 
              isProject={isProject} 
              onSearchByINN={handleSearchByINN}
              isSearching={isSearching} 
              getFieldIndicatorColor={getFieldIndicatorColor} 
            />

            <AddressFields 
              formData={companyFormData} 
              setFormData={setCompanyFormData} 
              errors={errors} 
              isEditing={isEditing} 
              isProject={isProject} 
              getFieldIndicatorColor={getFieldIndicatorColor} 
            />

            <ContactInfoFields 
              formData={companyFormData} 
              setFormData={setCompanyFormData} 
              errors={errors} 
              isEditing={isEditing} 
              getFieldIndicatorColor={getFieldIndicatorColor} 
            />
          </GlassCard>

          {/* Настройки Telegram группы С ЛОГОТИПОМ */}
          <GlassCard variant="default" padding="lg" className="border-white/10" hover={false}>
            <div className="space-y-6">
              <h3 className="text-text-white font-semibold text-xl mb-6 flex items-center gap-3">
                <TelegramIcon className="w-6 h-6 text-[#0088cc]" />
                Настройки Telegram-группы
              </h3>
              
              <div className="space-y-4">
                {/* Заголовок и логотип - grid layout: 2/3 для полей, 1/3 для логотипа */}
                <div className="grid md:grid-cols-3 gap-4 md:gap-6">
                  {/* Левая часть: поля - занимает 2 колонки */}
                  <div className="md:col-span-2 space-y-4">
                    <GlassInput 
                      label="Название группы"
                      value={supergroupFormData.title} 
                      onChange={e => setSupergroupFormData(prev => ({
                        ...prev,
                        title: e.target.value
                      }))} 
                      placeholder="Введите название группы" 
                      disabled={!isEditing} 
                      error={errors.title}
                      required 
                    />
                    
                    <GlassInput 
                      label="Описание группы" 
                      value={supergroupFormData.description} 
                      onChange={e => setSupergroupFormData(prev => ({
                        ...prev,
                        description: e.target.value
                      }))} 
                      placeholder="Введите описание группы" 
                      disabled={!isEditing} 
                      error={errors.description} 
                      required 
                    />
                  </div>
                  
                  {/* Правая часть: логотип - занимает 1 колонку и всю высоту */}
                  <div className="md:col-span-1 h-full">
                    <CompanyLogoUploader
                      value={supergroupFormData.company_logo}
                      onChange={(url) => setSupergroupFormData(prev => ({ 
                        ...prev, 
                        company_logo: url || '' 
                      }))}
                      disabled={!isEditing}
                      size="lg"
                      fill={true}
                      className="h-full"
                    />
                  </div>
                </div>

                {/* Остальные поля во всю ширину */}

                <div className="grid grid-cols-2 gap-4">
                  <GlassInput 
                    label="ID группы" 
                    value={supergroupId ? `-100${Math.abs(supergroupId)}` : ''} 
                    readOnly 
                    placeholder="ID группы"
                  />

                  <div className="relative">
                    <GlassInput 
                      label="Ссылка приглашения" 
                      value={supergroupFormData.invite_link || ''} 
                      placeholder="https://t.me/..." 
                      readOnly 
                    />
                    {supergroupFormData.invite_link && (
                      <button 
                        type="button" 
                        onClick={copyInviteLink} 
                        className="absolute right-3 top-[50%] -translate-y-1/2 p-1 text-text-muted hover:text-text-white transition-colors z-10" 
                        title="Копировать ссылку" 
                        style={{ top: 'calc(50% + 16px)' }}
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </GlassCard>

          {/* Кнопки действий */}
          <div className="flex justify-end gap-3 pt-6 border-t border-glass-border">
            <GlassButton type="button" variant="secondary" onClick={handleCancel} disabled={isSaving}>
              Закрыть
            </GlassButton>
            
            <GlassButton 
              onClick={handleSave} 
              disabled={!hasChanges || isSaving} 
              variant={hasChanges ? "primary" : "secondary"} 
              loading={isSaving}
            >
              {isSaving ? 'Сохранение...' : hasChanges ? 'Сохранить изменения' : 'Нет изменений'}
            </GlassButton>
          </div>
        </div>
      </DialogContent>
      
      {/* Standardized Duplicate Company Dialog */}
      <AppConfirmDialog
        open={showDuplicateDialog}
        onOpenChange={setShowDuplicateDialog}
        onConfirm={async () => {
          setIsSaving(true);
          try {
            // Привязываем супергруппу к существующей компании
            await telegramApi.updateSupergroup(supergroupId, {
              company_id: duplicateCompanyData.id
            });
            
            // Обновляем данные супергруппы
            const supergroupUpdates: any = {
              title: supergroupFormData.title,
              description: supergroupFormData.description,
              username: supergroupFormData.username,
              invite_link: supergroupFormData.invite_link,
              company_logo: supergroupFormData.company_logo
            };
            
            // Добавляем group_type только если он определен
            if (supergroupFormData.group_type) {
              supergroupUpdates.group_type = supergroupFormData.group_type;
            }
            await telegramApi.updateSupergroup(supergroupId, supergroupUpdates);
            
            toast({
              title: "Успешно",
              description: "Компания привязана к группе",
              variant: "success"
            });
            
            onSuccess?.();
            onClose();
          } catch (error) {
            logger.error('Error linking existing company', error, { component: 'EditCompanyGroupModal' });
            toast({
              title: "Ошибка",
              description: "Не удалось привязать компанию к группе",
              variant: "error"
            });
          } finally {
            setIsSaving(false);
          }
        }}
        title="Компания уже существует"
        description={
          duplicateCompanyData 
            ? `Компания "${duplicateCompanyData.name}"${duplicateCompanyData.vat ? ` (ИНН: ${duplicateCompanyData.vat})` : ''} уже существует в системе. Хотите привязать существующую компанию к группе?`
            : ''
        }
        confirmText="Привязать существующую"
        cancelText="Отмена"
        icon={Building}
      />
      
    </Dialog>
  );
};

export default EditCompanyGroupModal;
