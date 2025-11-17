import React, { useState } from 'react';
import { Users, Plus, Mail, Phone, MoreVertical, Shield, User, Crown } from 'lucide-react';
import { GlassCard, GlassButton } from '@/components/design-system';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';
import { logger } from '@/utils/logger';

interface Employee {
  id: string;
  name: string;
  email: string;
  phone: string;
  role: 'owner' | 'manager' | 'employee' | 'accountant';
  addedAt: string;
  avatar?: string;
}

const EmployeeManagement: React.FC = () => {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newEmployee, setNewEmployee] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'employee' as Employee['role']
  });

  // Mock data - будет заменено на реальные данные
  const [employees] = useState<Employee[]>([
    {
      id: '1',
      name: 'Иван Петров',
      email: 'ivan@company.com',
      phone: '+7 (999) 123-45-67',
      role: 'owner',
      addedAt: '2024-01-15',
      avatar: ''
    },
    {
      id: '2',
      name: 'Мария Сидорова',
      email: 'maria@company.com',
      phone: '+7 (999) 987-65-43',
      role: 'manager',
      addedAt: '2024-02-20',
      avatar: ''
    },
    {
      id: '3',
      name: 'Алексей Козлов',
      email: 'alexey@company.com',
      phone: '+7 (999) 456-78-90',
      role: 'employee',
      addedAt: '2024-03-10',
      avatar: ''
    },
    {
      id: '4',
      name: 'Елена Белова',
      email: 'elena@company.com',
      phone: '+7 (999) 321-54-76',
      role: 'accountant',
      addedAt: '2024-03-15',
      avatar: ''
    }
  ]);

  const getRoleIcon = (role: Employee['role']) => {
    switch (role) {
      case 'owner':
        return <Crown size={16} className="text-yellow-400" />;
      case 'manager':
        return <Shield size={16} className="text-gray-400" />;
      case 'accountant':
        return <Users size={16} className="text-green-400" />;
      default:
        return <User size={16} className="text-gray-400" />;
    }
  };

  const getRoleText = (role: Employee['role']) => {
    switch (role) {
      case 'owner':
        return 'Владелец';
      case 'manager':
        return 'Менеджер';
      case 'accountant':
        return 'Бухгалтер';
      default:
        return 'Сотрудник';
    }
  };

  const getRoleBadgeColor = (role: Employee['role']) => {
    switch (role) {
      case 'owner':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'manager':
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
      case 'accountant':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const handleAddEmployee = () => {
    // Здесь будет логика добавления сотрудника
    logger.debug('Adding employee', { employee: newEmployee, component: 'EmployeeManagement' });
    setIsAddDialogOpen(false);
    setNewEmployee({ name: '', email: '', phone: '', role: 'employee' });
  };

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users className="text-gray-400" size={24} />
          <h3 className="text-lg font-semibold text-white">Управление сотрудниками</h3>
        </div>
        
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <GlassButton className="flex items-center gap-2">
              <Plus size={16} />
              Добавить сотрудника
            </GlassButton>
          </DialogTrigger>
          <DialogContent className="bg-dark-gray border-white/20">
            <DialogHeader>
              <DialogTitle className="text-white">Добавить нового сотрудника</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Имя</label>
                <Input
                  placeholder="Введите полное имя"
                  value={newEmployee.name}
                  onChange={(e) => setNewEmployee({ ...newEmployee, name: e.target.value })}
                  className="bg-white/5 border-white/20 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Email</label>
                <Input
                  type="email"
                  placeholder="example@company.com"
                  value={newEmployee.email}
                  onChange={(e) => setNewEmployee({ ...newEmployee, email: e.target.value })}
                  className="bg-white/5 border-white/20 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Телефон</label>
                <Input
                  placeholder="+7 (999) 123-45-67"
                  value={newEmployee.phone}
                  onChange={(e) => setNewEmployee({ ...newEmployee, phone: e.target.value })}
                  className="bg-white/5 border-white/20 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Роль</label>
                <Select value={newEmployee.role} onValueChange={(value: Employee['role']) => setNewEmployee({ ...newEmployee, role: value })}>
                  <SelectTrigger className="bg-white/5 border-white/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-dark-gray border-white/20">
                    <SelectItem value="employee">Сотрудник</SelectItem>
                    <SelectItem value="manager">Менеджер</SelectItem>
                    <SelectItem value="accountant">Бухгалтер</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-3 pt-4">
                <Button onClick={handleAddEmployee} className="flex-1">
                  Добавить
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => setIsAddDialogOpen(false)}
                  className="flex-1"
                >
                  Отмена
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-3">
        {employees.map((employee) => (
          <div 
            key={employee.id} 
            className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-gradient-to-br from-medium-gray to-light-gray rounded-full flex items-center justify-center border border-white/10">
                <span className="text-white font-medium">
                  {employee.name.split(' ').map(n => n[0]).join('')}
                </span>
              </div>
              
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <h4 className="text-white font-medium">{employee.name}</h4>
                  <Badge className={`text-xs px-2 py-1 ${getRoleBadgeColor(employee.role)}`}>
                    <div className="flex items-center gap-1">
                      {getRoleIcon(employee.role)}
                      {getRoleText(employee.role)}
                    </div>
                  </Badge>
                </div>
                
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <div className="flex items-center gap-1">
                    <Mail size={14} />
                    {employee.email}
                  </div>
                  <div className="flex items-center gap-1">
                    <Phone size={14} />
                    {employee.phone}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">
                Добавлен {new Date(employee.addedAt).toLocaleDateString('ru-RU')}
              </span>
              
              {employee.role !== 'owner' && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                      <MoreVertical size={16} className="text-gray-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="bg-dark-gray border-white/20">
                    <DropdownMenuItem className="text-white hover:bg-white/10">
                      Изменить роль
                    </DropdownMenuItem>
                    <DropdownMenuItem className="text-white hover:bg-white/10">
                      Отправить приглашение
                    </DropdownMenuItem>
                    <DropdownMenuSeparator className="bg-white/20" />
                    <DropdownMenuItem className="text-red-400 hover:bg-red-500/10">
                      Удалить из компании
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        ))}
      </div>

      {employees.length === 0 && (
        <div className="text-center py-8">
          <Users className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h4 className="text-white font-medium mb-2">Нет сотрудников</h4>
          <p className="text-gray-400 text-sm">Добавьте первого сотрудника в компанию</p>
        </div>
      )}
    </GlassCard>
  );
};

export default EmployeeManagement;