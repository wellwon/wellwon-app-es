import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { GlassInput } from '@/components/design-system/GlassInput';
import { useToast } from '@/hooks/use-toast';
import { User, Mail, Edit3, Save, X, LogOut } from 'lucide-react';

const ProfileEditCard: React.FC = () => {
  const { user, profile, signOut, updateProfile } = useAuth();
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    first_name: profile?.first_name || '',
    last_name: profile?.last_name || '',
    bio: profile?.bio || '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSubmitting(true);
    
    try {
      const { error } = await updateProfile({
        first_name: formData.first_name,
        last_name: formData.last_name,
        bio: formData.bio,
      });

      if (error) {
        toast({
          title: 'Ошибка',
          description: 'Не удалось обновить профиль',
          variant: 'error',
        });
      } else {
        toast({
          title: 'Успешно',
          description: 'Профиль успешно обновлен',
          variant: 'success',
        });
        setIsEditing(false);
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Произошла неожиданная ошибка',
        variant: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      first_name: profile?.first_name || '',
      last_name: profile?.last_name || '',
      bio: profile?.bio || '',
    });
    setIsEditing(false);
  };

  const handleSignOut = async () => {
    const { error } = await signOut();
    if (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось выйти из системы',
        variant: 'error',
      });
    }
  };

  if (!user || !profile) {
    return (
      <GlassCard>
        <div className="text-center text-gray-400">
          Загрузка профиля...
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard variant="elevated" padding="lg">
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-accent-red/20 rounded-full flex items-center justify-center">
            <User className="w-8 h-8 text-accent-red" />
          </div>
          
          <div>
            <h2 className="text-xl font-bold text-white">
              {`${profile.first_name || ''} ${profile.last_name || ''}`.trim() || user.email}
            </h2>
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Mail className="w-4 h-4" />
              {user.email}
            </div>
            <div className="flex items-center gap-3 mt-2">
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                profile.active 
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                {profile.active ? 'Активен' : 'Неактивен'}
              </span>
              <span className="px-2 py-1 rounded-full text-xs font-medium bg-accent-red/20 text-accent-red border border-accent-red/30">
                {profile.is_developer ? 'Разработчик' : 'Менеджер'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isEditing ? (
            <GlassButton
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(true)}
              className="inline-flex items-center gap-2"
            >
              <Edit3 className="w-4 h-4" />
              Редактировать профиль
            </GlassButton>
          ) : (
            <div className="flex gap-2">
              <GlassButton
                variant="primary"
                size="sm"
                onClick={handleSave}
                loading={isSubmitting}
                className="inline-flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Сохранить профиль
              </GlassButton>
              
              <GlassButton
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                className="inline-flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                Отменить
              </GlassButton>
            </div>
          )}
        </div>
      </div>

      {isEditing ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          
          <div>
            <label className="block text-white text-sm font-medium mb-2">
              О себе
            </label>
            <textarea
              value={formData.bio}
              onChange={(e) => handleInputChange('bio', e.target.value)}
              placeholder="Расскажите о себе"
              className="w-full px-4 py-3 bg-gray-secondary/60 border border-white/10 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-accent-red/50 transition-colors resize-none"
              rows={3}
            />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-gray-400 text-sm mb-1">Имя</label>
            <p className="text-white">
              {profile.first_name || 'Не указано'}
            </p>
          </div>
          
          <div>
            <label className="block text-gray-400 text-sm mb-1">Фамилия</label>
            <p className="text-white">
              {profile.last_name || 'Не указано'}
            </p>
          </div>
          
          {profile.bio && (
            <div>
              <label className="block text-gray-400 text-sm mb-1">О себе</label>
              <p className="text-white">{profile.bio}</p>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 pt-6 border-t border-white/10">
        <GlassButton
          variant="secondary"
          onClick={handleSignOut}
          className="inline-flex items-center gap-2"
        >
          <LogOut className="w-4 h-4" />
          Выйти из системы
        </GlassButton>
      </div>
    </GlassCard>
  );
};

export default ProfileEditCard;