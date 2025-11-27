import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { adminApi, AdminUser } from '@/api/admin';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { useToast } from '@/hooks/use-toast';
import { Users, Shield, UserX, UserCheck } from 'lucide-react';
import { logger } from '@/utils/logger';

const UserManagement: React.FC = () => {
  const { profile } = useAuth();
  const { toast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);

  // Only WW managers and developers can manage users
  const canManageUsers = true; // All users are now managers/admins

  useEffect(() => {
    if (canManageUsers) {
      fetchUsers();
    } else {
      setLoading(false);
    }
  }, [canManageUsers]);

  const fetchUsers = async () => {
    try {
      const { data } = await adminApi.getUsers();
      // Filter users to only include developer types
      const filteredUsers = (data || []).filter(user =>
        user.developer === true
      );
      setUsers(filteredUsers);
    } catch (error) {
      logger.warn('[UserManagement] Admin users endpoint not available');
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список пользователей',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const updateUserStatus = async (userId: string, active: boolean) => {
    try {
      await adminApi.updateUser(userId, { active });

      setUsers(prev => prev.map(user =>
        user.user_id === userId ? { ...user, active } : user
      ));

      toast({
        title: 'Успешно',
        description: `Пользователь ${active ? 'активирован' : 'деактивирован'}`,
        variant: 'success',
      });
    } catch (error) {
      logger.error('[UserManagement] Failed to update user status', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось обновить статус пользователя',
        variant: 'error',
      });
    }
  };

  const updateUserType = async (userId: string, isDeveloper: boolean) => {
    try {
      await adminApi.updateUser(userId, { developer: isDeveloper });

      setUsers(prev => prev.map(user =>
        user.user_id === userId ? { ...user, developer: isDeveloper } : user
      ));

      toast({
        title: 'Успешно',
        description: 'Тип пользователя обновлен',
        variant: 'success',
      });
    } catch (error) {
      logger.error('[UserManagement] Failed to update user type', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось обновить тип пользователя',
        variant: 'error',
      });
    }
  };

  const getTypeLabel = (isDeveloper: boolean) => {
    return isDeveloper ? 'Разработчик WW' : 'Пользователь WW';
  };

  if (!canManageUsers) {
    return (
      <GlassCard>
        <div className="text-center text-gray-400">
          <Shield className="w-12 h-12 mx-auto mb-4 text-gray-600" />
          <p>У вас нет прав для управления пользователями</p>
        </div>
      </GlassCard>
    );
  }

  if (loading) {
    return (
      <GlassCard>
        <div className="text-center text-gray-400">
          Загрузка пользователей...
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <div className="flex items-center gap-3 mb-6">
        <Users className="w-6 h-6 text-accent-red" />
        <h2 className="text-xl font-bold text-white">Управление пользователями</h2>
      </div>

      <div className="space-y-4">
        {users.map((user) => (
          <div
            key={user.id}
            className="bg-gray-secondary/40 border border-white/10 rounded-xl p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-white font-medium">
                    {`${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Без имени'}
                  </h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    user.active
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-red-500/20 text-red-400 border border-red-500/30'
                  }`}>
                    {user.active ? 'Активный' : 'Неактивный'}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span>Тип: {getTypeLabel(user.developer)}</span>
                  <span>Создан: {new Date(user.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={user.developer ? 'developer' : 'user'}
                  onChange={(e) => updateUserType(user.user_id, e.target.value === 'developer')}
                  className="px-3 py-1 bg-gray-secondary/60 border border-white/10 rounded-lg text-white text-sm"
                >
                  <option value="user">Пользователь WW</option>
                  <option value="developer">Разработчик WW</option>
                </select>

                <GlassButton
                  variant={user.active ? "outline" : "primary"}
                  size="sm"
                  onClick={() => updateUserStatus(user.user_id, !user.active)}
                  className={`inline-flex items-center gap-2 ${
                    user.active
                      ? 'text-red-400 border-red-400/30 hover:bg-red-400/10'
                      : 'text-green-400 border-green-400/30 hover:bg-green-400/10'
                  }`}
                >
                  {user.active ? (
                    <>
                      <UserX className="w-4 h-4" />
                      Деактивировать
                    </>
                  ) : (
                    <>
                      <UserCheck className="w-4 h-4" />
                      Активировать
                    </>
                  )}
                </GlassButton>
              </div>
            </div>
          </div>
        ))}

        {users.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            Пользователи не найдены
          </div>
        )}
      </div>
    </GlassCard>
  );
};

export default UserManagement;
