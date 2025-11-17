import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, Building, Users, Settings, Shield } from 'lucide-react';
import { AdminFormsModal } from './AdminFormsModal';

const AdminActionsContent: React.FC = () => {
  const [selectedForm, setSelectedForm] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    accounts: true,
    companies: true
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  return (
    <>
      <div className="space-y-3">
        {/* Управление аккаунтами - сворачиваемый раздел */}
        <div className="space-y-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full h-8 text-sm font-medium text-white hover:bg-white/5 justify-start p-2"
            onClick={() => toggleSection('accounts')}
          >
            {expandedSections.accounts ? (
              <ChevronDown className="w-4 h-4 mr-2" />
            ) : (
              <ChevronRight className="w-4 h-4 mr-2" />
            )}
            <Building className="w-4 h-4 mr-2" />
            Управление аккаунтами
          </Button>
          
          {expandedSections.accounts && (
            <div className="pl-8 space-y-1">
              <Button
                variant="secondary"
                size="sm"
                className="w-full h-7 text-xs justify-start"
                onClick={() => setSelectedForm('user-management')}
              >
                Управление пользователями
              </Button>
            </div>
          )}
        </div>

        {/* Управление компаниями - сворачиваемый раздел */}
        <div className="space-y-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full h-8 text-sm font-medium text-white hover:bg-white/5 justify-start p-2"
            onClick={() => toggleSection('companies')}
          >
            {expandedSections.companies ? (
              <ChevronDown className="w-4 h-4 mr-2" />
            ) : (
              <ChevronRight className="w-4 h-4 mr-2" />
            )}
            <Users className="w-4 h-4 mr-2" />
            Управление компаниями
          </Button>
          
          {expandedSections.companies && (
            <div className="pl-8 space-y-1">
              <Button
                variant="secondary"
                size="sm"
                className="w-full h-7 text-xs justify-start"
                onClick={() => setSelectedForm('system-settings')}
              >
                <Settings className="w-3 h-3 mr-2" />
                Системные настройки
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="w-full h-7 text-xs justify-start"
                onClick={() => setSelectedForm('security-check')}
              >
                <Shield className="w-3 h-3 mr-2" />
                Проверка безопасности
              </Button>
            </div>
          )}
        </div>
      </div>

      <AdminFormsModal
        isOpen={!!selectedForm}
        onClose={() => setSelectedForm(null)}
        formType={selectedForm}
      />
    </>
  );
};

export default AdminActionsContent;