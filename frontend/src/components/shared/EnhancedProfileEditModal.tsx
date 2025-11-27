import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '@/contexts/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { GlassCard } from '@/components/design-system/GlassCard';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { X, Upload, Eye, EyeOff, Check, Camera } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { GlassButton } from '@/components/design-system/GlassButton';
import { GlassInput } from '@/components/design-system/GlassInput';
import { logger } from '@/utils/logger';

interface ProfileEditModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface FormData {
  first_name: string;
  last_name: string;
  phone: string;
  bio: string;
  avatar_url: string;
}

interface PasswordData {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export const EnhancedProfileEditModal: React.FC<ProfileEditModalProps> = ({ isOpen, onClose }) => {
  const { user, profile, updateProfile, updatePassword } = useAuth();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showPasswordSection, setShowPasswordSection] = useState(false);
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });

  // Форма профиля
  const [formData, setFormData] = useState<FormData>({
    first_name: '',
    last_name: '',
    phone: '',
    bio: '',
    avatar_url: ''
  });

  // Исходные данные для сравнения изменений
  const [initialData, setInitialData] = useState<FormData>({
    first_name: '',
    last_name: '',
    phone: '',
    bio: '',
    avatar_url: ''
  });

  // Форма паролей
  const [passwordData, setPasswordData] = useState<PasswordData>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  // Инициализация данных формы при открытии модала
  useEffect(() => {
    logger.debug('Profile form initialization', { isOpen, profile: !!profile, component: 'EnhancedProfileEditModal' });
    
    if (isOpen && profile) {
      logger.debug('Profile data for initialization', {
        hasFirstName: !!profile.first_name,
        hasLastName: !!profile.last_name,
        hasPhone: !!profile.phone,
        hasBio: !!profile.bio,
        hasAvatar: !!profile.avatar_url,
        active: profile.active,
        component: 'EnhancedProfileEditModal'
      });
      
      const initialFormData = {
        first_name: profile.first_name || '',
        last_name: profile.last_name || '',
        phone: profile.phone || '',
        bio: profile.bio || '',
        avatar_url: profile.avatar_url || ''
      };
      
      logger.debug('Setting form data', { component: 'EnhancedProfileEditModal' });
      setFormData(initialFormData);
      setInitialData(initialFormData);
      setIsEditing(true); // Сразу включаем редактирование
    } else if (isOpen && !profile) {
      logger.warn('Modal opened but profile not loaded', { component: 'EnhancedProfileEditModal' });
    }
  }, [isOpen, profile]);

  // Сброс состояния при закрытии модала
  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
      setShowPasswordSection(false);
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      });
    }
  }, [isOpen]);

  // Проверка наличия изменений в форме
  const hasChanges = () => {
    return JSON.stringify(formData) !== JSON.stringify(initialData);
  };

  // Проверка валидности пароля
  const isPasswordValid = () => {
    return passwordData.newPassword.length >= 6 && 
           passwordData.newPassword === passwordData.confirmPassword &&
           passwordData.currentPassword.length > 0;
  };

  const handleInputChange = (field: keyof FormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handlePasswordChange = (field: keyof PasswordData, value: string) => {
    setPasswordData(prev => ({ ...prev, [field]: value }));
  };

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !user) return;

    // Валидация файла
    if (!file.type.startsWith('image/')) {
      toast({
        title: "Ошибка",
        description: "Пожалуйста, выберите изображение",
        variant: "error"
      });
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "Ошибка",
        description: "Размер файла не должен превышать 5 МБ",
        variant: "error"
      });
      return;
    }

    setIsLoading(true);

    try {
      const fileExt = file.name.split('.').pop();
      const fileName = `${user.id}/${Date.now()}.${fileExt}`;

      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(fileName, file, { upsert: true });

      if (uploadError) throw uploadError;

      const { data } = supabase.storage
        .from('avatars')
        .getPublicUrl(fileName);

      setFormData(prev => ({ ...prev, avatar_url: data.publicUrl }));

      toast({
        title: "Успех",
        description: "Аватар успешно загружен",
        variant: "success"
      });
    } catch (error) {
      logger.error('Avatar upload error', error, { component: 'EnhancedProfileEditModal' });
      toast({
        title: "Ошибка",
        description: "Не удалось загрузить аватар",
        variant: "error"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!hasChanges() && !showPasswordSection) return;

    setIsLoading(true);

    try {
      // Сохраняем изменения профиля
      if (hasChanges()) {
        const { error: profileError } = await updateProfile(formData);
        if (profileError) throw profileError;
      }

      // Сохраняем новый пароль если введен
      if (showPasswordSection && isPasswordValid()) {
        const { error: passwordError } = await updatePassword(
          passwordData.currentPassword,
          passwordData.newPassword
        );
        if (passwordError) throw passwordError;
      }

      toast({
        title: "Успех",
        description: "Профиль успешно обновлен",
        variant: "success"
      });

      // Обновляем исходные данные
      setInitialData(formData);
      setIsEditing(false);
      setShowPasswordSection(false);
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      });
    } catch (error: any) {
      logger.error('Profile save error', error, { component: 'EnhancedProfileEditModal' });
      toast({
        title: "Ошибка",
        description: error.message || "Не удалось сохранить изменения",
        variant: "error"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    onClose();
  };

  const getUserDisplayName = () => {
    if (profile?.first_name || profile?.last_name) {
      return `${profile?.first_name || ''} ${profile?.last_name || ''}`.trim();
    }
    return user?.email?.split('@')[0] || 'Пользователь';
  };

  const getUserTypeLabel = () => {
    const typeLabels = {
      ww_manager: 'Менеджер WW',
      ww_developer: 'Разработчик WW'
    };
    return profile?.is_developer ? 'Разработчик' : 'Менеджер';
  };

  const getUserInitials = () => {
    const name = getUserDisplayName();
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-2xl max-h-[90vh]">
        <GlassCard variant="elevated" className="w-full h-auto bg-background/95 backdrop-blur-lg border border-white/20 flex flex-col" hover={false}>
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <h2 className="text-xl font-semibold text-foreground">
              Настройки профиля
            </h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>

          <div className="flex-1 p-6 space-y-4">
            {/* Avatar Section */}
            <div className="flex items-center space-x-4">
              <div className="relative group">
                <Avatar 
                  className="w-16 h-16 cursor-pointer transition-all duration-200"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <AvatarImage src={formData.avatar_url} />
                  <AvatarFallback className="text-lg font-semibold bg-primary/20 text-primary">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
                
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center cursor-pointer"
                     onClick={() => fileInputRef.current?.click()}>
                  <Camera className="w-6 h-6 text-white" />
                </div>
                
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarUpload}
                  className="hidden"
                />
              </div>

              <div className="flex-1">
                <h3 className="text-lg font-semibold text-foreground">
                  {getUserDisplayName()}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {getUserTypeLabel()}
                </p>
                <p className="text-sm text-muted-foreground">
                  {user?.email}
                </p>
              </div>

              <GlassButton
                variant="secondary"
                size="sm"
                onClick={() => setShowPasswordSection(!showPasswordSection)}
              >
                {showPasswordSection ? 'Скрыть' : 'Изменить пароль'}
              </GlassButton>
            </div>

            {/* Profile Fields */}
            <div className="space-y-4">
              {/* Имя и Фамилия в одной строке */}
              <div className="grid grid-cols-2 gap-4">
                <GlassInput
                  label="Имя"
                  value={formData.first_name}
                  onChange={(e) => handleInputChange('first_name', e.target.value)}
                  placeholder="Введите имя"
                />

                <GlassInput
                  label="Фамилия"
                  value={formData.last_name}
                  onChange={(e) => handleInputChange('last_name', e.target.value)}
                  placeholder="Введите фамилию"
                />
              </div>

              {/* Email и Телефон в одной строке */}
              <div className="grid grid-cols-2 gap-4">
                <GlassInput
                  label="Email"
                  value={user?.email || ''}
                  disabled
                  placeholder="Email адрес"
                />

                <GlassInput
                  label="Телефон"
                  value={formData.phone}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                  placeholder="Введите номер телефона"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-white">О себе</label>
                <textarea
                  value={formData.bio}
                  onChange={(e) => handleInputChange('bio', e.target.value)}
                  placeholder="Расскажите о себе..."
                  className="glass-input flex min-h-[60px] w-full rounded-xl border border-white/10 bg-[#1a1a1d] backdrop-blur-sm px-4 py-3 text-sm text-white placeholder:text-sm placeholder:text-gray-400 transition-all duration-300 focus-visible:outline-none hover:border-white/20 focus:border-accent-red disabled:cursor-not-allowed disabled:opacity-50 resize-none"
                />
              </div>
            </div>

            {/* Password Section */}
            {showPasswordSection && (
              <div className="space-y-3">
                <h3 className="text-lg font-medium">Смена пароля</h3>

                <div className="grid grid-cols-1 gap-3 p-3 bg-[#1a1a1d]/30 rounded-lg border border-white/10">
                  <GlassInput
                    label="Текущий пароль"
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) => handlePasswordChange('currentPassword', e.target.value)}
                    placeholder="Введите текущий пароль"
                    showPasswordToggle
                  />

                  <div>
                    <GlassInput
                      label="Новый пароль"
                      type="password"
                      value={passwordData.newPassword}
                      onChange={(e) => handlePasswordChange('newPassword', e.target.value)}
                      placeholder="Введите новый пароль"
                      showPasswordToggle
                    />
                    {passwordData.newPassword && passwordData.newPassword.length < 6 && (
                      <p className="text-sm text-accent-red mt-1">Пароль должен содержать минимум 6 символов</p>
                    )}
                  </div>

                  <div>
                    <GlassInput
                      label="Подтвердите новый пароль"
                      type="password"
                      value={passwordData.confirmPassword}
                      onChange={(e) => handlePasswordChange('confirmPassword', e.target.value)}
                      placeholder="Повторите новый пароль"
                      showPasswordToggle
                      success={passwordData.confirmPassword && passwordData.newPassword === passwordData.confirmPassword && passwordData.newPassword.length >= 6}
                      error={passwordData.confirmPassword && passwordData.newPassword !== passwordData.confirmPassword ? "Пароли не совпадают" : undefined}
                    />
                  </div>
                </div>
              </div>
            )}

            </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 p-6 border-t border-white/10">
            <GlassButton
              variant="secondary"
              onClick={handleCancel}
              disabled={isLoading}
            >
              Закрыть
            </GlassButton>
            <GlassButton
              onClick={handleSave}
              disabled={isLoading || (!hasChanges() && (!showPasswordSection || !isPasswordValid()))}
              loading={isLoading}
            >
              Сохранить
            </GlassButton>
          </div>
        </GlassCard>
      </div>
    </div>,
    document.body
  );
};