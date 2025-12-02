// =============================================================================
// References Content - Справочники декларанта (рабочая область)
// =============================================================================
// Компонент для отображения внутри DeclarantContent
// Карточки справочников с возможностью провалиться в детальный просмотр

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database,
  RefreshCw,
  FileJson,
  CheckCircle,
  AlertCircle,
  Search,
  ChevronRight,
  ChevronDown,
  Layers,
  Code,
  FileEdit,
  Building2,
  FileText,
  ClipboardList,
  Package,
  Coins,
  Factory,
  Ruler,
  Star,
  Users,
  Building,
  UserCheck,
  FileStack,
  LucideIcon,
  Hammer
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { API } from '@/api/core';

// =============================================================================
// Types
// =============================================================================

interface ReferenceInfo {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  count: number;
  unique_count?: number;
  last_updated: string | null;
  // Extended API info
  api_source?: string;
  api_endpoint?: string;
  // Database table name
  table_name?: string;
}

interface JsonTemplate {
  id: string;
  gf_code: string;
  document_mode_id: string;
  type_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  sections_count?: number; // Количество секций в форме (0 = форма не настроена)
  document_type_code?: string | null; // Код вида документа (связь с dc_document_types)
}

interface CustomsOffice {
  id: string;
  kontur_id: string;
  code: string | null;
  short_name: string | null;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface DeclarationType {
  id: string;
  kontur_id: number;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Procedure {
  id: string;
  kontur_id: number;
  declaration_type_id: number;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Static reference types
interface PackagingGroup {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Currency {
  id: string;
  code: string;
  alpha_code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface EnterpriseCategory {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface MeasurementUnit {
  id: string;
  code: string;
  short_name: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface DeclarationFeature {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface DocumentType {
  id: string;
  code: string;
  name: string;
  ed_documents: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// API справочники - Контрагенты и Подписанты
interface CommonOrg {
  id: string;
  kontur_id: string;
  org_name: string | null;
  short_name: string | null;
  org_type: number;
  inn: string | null;
  kpp: string | null;
  ogrn: string | null;
  is_foreign: boolean;
  legal_address: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Organization {
  id: string;
  kontur_id: string;
  name: string | null;
  inn: string | null;
  kpp: string | null;
  ogrn: string | null;
  address: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Employee {
  id: string;
  kontur_id: string;
  organization_id: string | null;
  surname: string | null;
  name: string | null;
  patronymic: string | null;
  phone: string | null;
  email: string | null;
  auth_letter_date: string | null;
  auth_letter_number: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface JsonTemplatesResponse {
  items: JsonTemplate[];
  total: number;
  unique_forms: number;
  last_updated: string | null;
}

interface CustomsResponse {
  items: CustomsOffice[];
  total: number;
  last_updated: string | null;
}

interface DeclarationTypesResponse {
  items: DeclarationType[];
  total: number;
  last_updated: string | null;
}

interface ProceduresResponse {
  items: Procedure[];
  total: number;
  unique_codes: number;
  last_updated: string | null;
}

// Static reference responses
interface PackagingGroupsResponse {
  items: PackagingGroup[];
  total: number;
  last_updated: string | null;
}

interface CurrenciesResponse {
  items: Currency[];
  total: number;
  last_updated: string | null;
}

interface EnterpriseCategoriesResponse {
  items: EnterpriseCategory[];
  total: number;
  last_updated: string | null;
}

interface MeasurementUnitsResponse {
  items: MeasurementUnit[];
  total: number;
  last_updated: string | null;
}

interface DeclarationFeaturesResponse {
  items: DeclarationFeature[];
  total: number;
  last_updated: string | null;
}

interface DocumentTypesResponse {
  items: DocumentType[];
  total: number;
  last_updated: string | null;
}

// API reference responses
interface CommonOrgsResponse {
  items: CommonOrg[];
  total: number;
  last_updated: string | null;
}

interface OrganizationsResponse {
  items: Organization[];
  total: number;
  last_updated: string | null;
}

interface EmployeesResponse {
  items: Employee[];
  total: number;
  last_updated: string | null;
}

interface SyncResult {
  success: boolean;
  total_fetched: number;
  inserted: number;
  updated: number;
  skipped: number;
  errors: number;
  sync_time: string;
  message: string;
}

interface ReferencesContentProps {
  isDark: boolean;
  activeReferenceId?: string | null;
  onReferenceNavigate?: (referenceId: string | null) => void;
}

// =============================================================================
// API Functions
// =============================================================================

const API_BASE = '/declarant/references';

async function fetchReferences(): Promise<ReferenceInfo[]> {
  const response = await API.get<{ references: ReferenceInfo[] }>(API_BASE);
  return response.data.references;
}

async function fetchJsonTemplates(): Promise<JsonTemplatesResponse> {
  const response = await API.get<JsonTemplatesResponse>(`${API_BASE}/json-templates`);
  return response.data;
}

async function syncJsonTemplates(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/json-templates/sync`);
  return response.data;
}

async function fetchTemplateSchema(documentModeId: string): Promise<Record<string, unknown>> {
  const response = await API.get<{ document_mode_id: string; schema: Record<string, unknown> }>(
    `${API_BASE}/json-templates/${documentModeId}/schema`
  );
  return response.data.schema;
}

// Customs API
async function fetchCustoms(): Promise<CustomsResponse> {
  const response = await API.get<CustomsResponse>(`${API_BASE}/customs`);
  return response.data;
}

async function syncCustoms(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/customs/sync`);
  return response.data;
}

// Declaration Types API
async function fetchDeclarationTypes(): Promise<DeclarationTypesResponse> {
  const response = await API.get<DeclarationTypesResponse>(`${API_BASE}/declaration-types`);
  return response.data;
}

async function syncDeclarationTypes(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/declaration-types/sync`);
  return response.data;
}

// Procedures API
async function fetchProcedures(declarationTypeId?: number): Promise<ProceduresResponse> {
  const params = declarationTypeId !== undefined ? `?declaration_type_id=${declarationTypeId}` : '';
  const response = await API.get<ProceduresResponse>(`${API_BASE}/procedures${params}`);
  return response.data;
}

async function syncProcedures(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/procedures/sync`);
  return response.data;
}

// Static References API
async function fetchPackagingGroups(): Promise<PackagingGroupsResponse> {
  const response = await API.get<PackagingGroupsResponse>(`${API_BASE}/packaging-groups`);
  return response.data;
}

async function fetchCurrencies(): Promise<CurrenciesResponse> {
  const response = await API.get<CurrenciesResponse>(`${API_BASE}/currencies`);
  return response.data;
}

async function fetchEnterpriseCategories(): Promise<EnterpriseCategoriesResponse> {
  const response = await API.get<EnterpriseCategoriesResponse>(`${API_BASE}/enterprise-categories`);
  return response.data;
}

async function fetchMeasurementUnits(): Promise<MeasurementUnitsResponse> {
  const response = await API.get<MeasurementUnitsResponse>(`${API_BASE}/measurement-units`);
  return response.data;
}

async function fetchDeclarationFeatures(): Promise<DeclarationFeaturesResponse> {
  const response = await API.get<DeclarationFeaturesResponse>(`${API_BASE}/declaration-features`);
  return response.data;
}

async function syncDeclarationFeatures(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/declaration-features/sync`);
  return response.data;
}

async function fetchDocumentTypes(): Promise<DocumentTypesResponse> {
  const response = await API.get<DocumentTypesResponse>(`${API_BASE}/document-types`);
  return response.data;
}

// API References - Контрагенты и Подписанты
async function fetchCommonOrgs(): Promise<CommonOrgsResponse> {
  const response = await API.get<CommonOrgsResponse>(`${API_BASE}/common-orgs`);
  return response.data;
}

async function syncCommonOrgs(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/common-orgs/sync`);
  return response.data;
}

async function fetchOrganizations(): Promise<OrganizationsResponse> {
  const response = await API.get<OrganizationsResponse>(`${API_BASE}/organizations`);
  return response.data;
}

async function syncOrganizations(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/organizations/sync`);
  return response.data;
}

async function fetchEmployees(): Promise<EmployeesResponse> {
  const response = await API.get<EmployeesResponse>(`${API_BASE}/employees`);
  return response.data;
}

async function syncEmployees(): Promise<SyncResult> {
  const response = await API.post<SyncResult>(`${API_BASE}/employees/sync`);
  return response.data;
}

// =============================================================================
// Helper Functions
// =============================================================================

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

const getErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object') {
    const axiosErr = err as { response?: { data?: { detail?: string } }, message?: string };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  return 'Неизвестная ошибка';
};

// =============================================================================
// ReferenceCard Component
// =============================================================================

interface ReferenceCardProps {
  reference: ReferenceInfo;
  isDark: boolean;
  onClick: () => void;
}

// Icon mapping for references
const referenceIcons: Record<string, LucideIcon> = {
  'json-templates': FileJson,
  'customs': Building2,
  'declaration-types': FileText,
  'procedures': ClipboardList,
  'packaging-groups': Package,
  'currencies': Coins,
  'enterprise-categories': Factory,
  'measurement-units': Ruler,
  'declaration-features': Star,
  'document-types': FileStack,
  'common-orgs': Users,
  'organizations': Building,
  'employees': UserCheck,
};

// Редактируемые справочники (ведутся в приложении, не только синхронизируются из API)
const editableReferenceIds = ['organizations', 'common-orgs', 'employees'];

const ReferenceCard: React.FC<ReferenceCardProps> = ({ reference, isDark, onClick }) => {
  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10 hover:border-white/20',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
      muted: 'text-gray-500'
    },
    icon: 'bg-white/5',
    badge: 'bg-white/10 text-gray-300'
  } : {
    card: 'bg-white border-gray-300 hover:border-gray-400 shadow-sm',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-gray-600',
      muted: 'text-gray-400'
    },
    icon: 'bg-gray-100',
    badge: 'bg-gray-100 text-gray-600'
  };

  const IconComponent = referenceIcons[reference.id] || Database;
  const isApiReference = !!reference.api_source;
  const isEditableReference = editableReferenceIds.includes(reference.id);

  // Стили иконки:
  // - зеленая для редактируемых справочников (Организации, Контрагенты, Подписанты)
  // - фиолетовая для API справочников
  // - обычная для остальных
  let iconBg: string;
  let iconColor: string;

  // Специальный стиль для json-templates - красная иконка
  const isJsonTemplates = reference.id === 'json-templates';

  if (isJsonTemplates) {
    iconBg = 'bg-accent-red/15';
    iconColor = 'text-accent-red';
  } else if (isEditableReference) {
    iconBg = 'bg-[#22c55e]/15';
    iconColor = 'text-[#22c55e]';
  } else if (isApiReference) {
    iconBg = 'bg-[#6366f1]/15';
    iconColor = 'text-[#6366f1]';
  } else {
    iconBg = theme.icon;
    iconColor = theme.text.secondary;
  }

  return (
    <button
      onClick={onClick}
      className={`w-full p-4 rounded-2xl border transition-colors text-left ${theme.card}`}
    >
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${iconBg}`}>
          <IconComponent className={`w-5 h-5 ${iconColor}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`font-semibold ${theme.text.primary}`}>{reference.name}</h3>
            {reference.api_source && (
              <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${theme.badge}`}>
                {reference.api_source}
              </span>
            )}
          </div>
          <p className={`text-sm mt-0.5 ${theme.text.secondary}`}>{reference.description}</p>
          {reference.api_endpoint && (
            <p className={`text-xs mt-1 font-mono ${theme.text.muted}`}>
              {reference.api_endpoint}
            </p>
          )}
          <div className={`flex items-center justify-between mt-2 text-sm ${theme.text.muted}`}>
            <span className="flex items-center gap-1">
              <Layers size={14} />
              {reference.count} записей
              {reference.unique_count && reference.unique_count !== reference.count && (
                <span className={theme.text.secondary}>({reference.unique_count} форм)</span>
              )}
            </span>
            {reference.last_updated && (
              <span>Обновлено: {formatDate(reference.last_updated)}</span>
            )}
            {reference.table_name && (
              <span className="font-mono text-xs">{reference.table_name}</span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
};

// =============================================================================
// JsonTemplatesDetail Component
// =============================================================================

interface JsonTemplatesDetailProps {
  isDark: boolean;
}

const JsonTemplatesDetail: React.FC<JsonTemplatesDetailProps> = ({ isDark }) => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<JsonTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [uniqueForms, setUniqueForms] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Expanded rows state
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [loadingSchemas, setLoadingSchemas] = useState<Set<string>>(new Set());
  const [schemas, setSchemas] = useState<Record<string, Record<string, unknown>>>({});

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
      muted: 'text-gray-500'
    },
    button: {
      primary: 'bg-accent-red text-white hover:bg-accent-red/90',
      ghost: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10'
    },
    table: {
      header: 'bg-white/5 border-white/10 text-gray-400',
      row: 'border-white/10 hover:bg-white/[0.03]',
      cell: 'text-white'
    },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-gray-600',
      muted: 'text-gray-400'
    },
    button: {
      primary: 'bg-accent-red text-white hover:bg-accent-red/90 shadow-sm',
      ghost: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100'
    },
    table: {
      header: 'bg-gray-50 border-gray-200 text-gray-500',
      row: 'border-gray-200 hover:bg-[#f4f4f6]',
      cell: 'text-gray-900'
    },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadTemplates = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchJsonTemplates();
      setTemplates(data.items);
      setTotal(data.total);
      setUniqueForms(data.unique_forms);
      setLastUpdated(data.last_updated);
    } catch (err) {
      console.error('Error loading templates:', err);
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncResult(null);
    try {
      const result = await syncJsonTemplates();
      setSyncResult(result);
      await loadTemplates();
      // Auto-hide sync result after 3 seconds
      setTimeout(() => setSyncResult(null), 3000);
    } catch (err) {
      console.error('Error syncing templates:', err);
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Toggle row expansion and load schema
  const toggleRow = async (templateId: string) => {
    const newExpanded = new Set(expandedRows);

    // Find the template to get its document_mode_id for schema loading
    const template = templates.find(t => t.id === templateId);
    const documentModeId = template?.document_mode_id;

    if (newExpanded.has(templateId)) {
      // Collapse
      newExpanded.delete(templateId);
    } else {
      // Expand
      newExpanded.add(templateId);

      // Load schema if not already loaded (by document_mode_id)
      if (documentModeId && !schemas[documentModeId] && !loadingSchemas.has(documentModeId)) {
        setLoadingSchemas(prev => new Set(prev).add(documentModeId));
        try {
          const schema = await fetchTemplateSchema(documentModeId);
          setSchemas(prev => ({ ...prev, [documentModeId]: schema }));
        } catch (err) {
          console.error(`Error loading schema for ${documentModeId}:`, err);
        } finally {
          setLoadingSchemas(prev => {
            const next = new Set(prev);
            next.delete(documentModeId);
            return next;
          });
        }
      }
    }

    setExpandedRows(newExpanded);
  };

  const filteredTemplates = templates.filter(t =>
    t.type_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.document_mode_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.gf_code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Sort templates by gf_code, then by type_name alphabetically
  const sortedTemplates = [...filteredTemplates].sort((a, b) => {
    const gfCompare = a.gf_code.localeCompare(b.gf_code);
    if (gfCompare !== 0) return gfCompare;
    return a.type_name.localeCompare(b.type_name, 'ru');
  });

  // Create color map for document_mode_id grouping
  const documentModeColors = React.useMemo(() => {
    const colors = [
      'text-blue-500',
      'text-purple-500',
      'text-emerald-500',
      'text-orange-500',
      'text-pink-500',
      'text-cyan-500',
      'text-yellow-500',
      'text-indigo-500',
      'text-rose-500',
      'text-teal-500',
    ];
    const uniqueModes = [...new Set(sortedTemplates.map(t => t.document_mode_id))];
    const colorMap: Record<string, string> = {};
    uniqueModes.forEach((mode, index) => {
      colorMap[mode] = colors[index % colors.length];
    });
    return colorMap;
  }, [sortedTemplates]);

  // Handler for opening Form Builder
  const handleOpenFormBuilder = (documentModeId: string, gfCode: string, typeName: string) => {
    // Navigate to Form Builder with document mode parameters
    navigate(`/declarant/form-builder/new?documentModeId=${documentModeId}&gfCode=${gfCode}&typeName=${encodeURIComponent(typeName)}`);
  };

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className={`text-2xl font-bold ${theme.text.primary}`}>
            Шаблоны JSON форм
          </h2>
          <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${
            isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'
          }`}>
            Kontur.Declarant API
          </span>
          <span className={`text-sm ${theme.text.secondary}`}>
            {total} записей ({uniqueForms} уникальных форм)
            {lastUpdated && <> | Обновлено: {formatDate(lastUpdated)}</>}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-md font-mono bg-accent-red/10 text-accent-red">
            GET /common/v1/jsonTemplates
          </span>
        </div>

        <button
          onClick={handleSync}
          disabled={isSyncing}
          className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium ${theme.button.primary}`}
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Загрузка...' : 'Обновить'}
        </button>
      </div>

      {/* Sync Result */}
      {syncResult && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${
          syncResult.success
            ? isDark ? 'bg-green-500/10 text-green-500' : 'bg-green-50 text-green-700'
            : isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'
        }`}>
          {syncResult.success ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm">{syncResult.message}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${
          isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'
        }`}>
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input
          placeholder="Поиск по названию, ID формы или коду..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={`pl-10 h-10 rounded-xl border ${theme.input}`}
        />
      </div>

      {/* Table */}
      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} />
          </div>
        ) : sortedTemplates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>
              {searchQuery ? 'Ничего не найдено' : 'Нет данных. Нажмите "Обновить" для загрузки'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">
                    Код GF
                  </th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-32">
                    ID формы
                  </th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">
                    Название шаблона
                  </th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">
                    Код док.
                  </th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-40">
                    Обновлено
                  </th>
                  <th className="py-3 px-4 text-right text-xs font-medium uppercase tracking-wider w-32">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedTemplates.map((template, index) => {
                  const isExpanded = expandedRows.has(template.id);
                  const isLoadingSchema = loadingSchemas.has(template.document_mode_id);
                  const schema = schemas[template.document_mode_id];
                  const isLast = index === sortedTemplates.length - 1;

                  return (
                    <React.Fragment key={template.id}>
                      {/* Main row - clickable to expand */}
                      <tr
                        onClick={() => toggleRow(template.id)}
                        className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}
                      >
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isLoadingSchema && isExpanded ? (
                              <RefreshCw className="w-4 h-4 animate-spin" />
                            ) : isExpanded ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>
                          {template.gf_code}
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-semibold ${documentModeColors[template.document_mode_id]}`}>
                          {template.document_mode_id}
                        </td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>
                          {template.type_name}
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono ${template.document_type_code ? 'text-emerald-500' : theme.text.muted}`}>
                          {template.document_type_code || '—'}
                        </td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>
                          {formatDate(template.updated_at)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {/* Зелёная кнопка если есть секции (форма настроена), красная - если нет */}
                          {(() => {
                            const hasForms = ((template as JsonTemplate & { sections_count?: number }).sections_count ?? 0) > 0;
                            const buttonStyle = hasForms
                              ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 hover:bg-emerald-500/20'
                              : 'bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20';
                            return (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenFormBuilder(template.document_mode_id, template.gf_code, template.type_name);
                                }}
                                className={`inline-flex items-center gap-1.5 px-3 h-8 rounded-lg text-sm font-medium transition-colors ${buttonStyle}`}
                              >
                                <Hammer className="w-4 h-4" />
                                Конструктор
                              </button>
                            );
                          })()}
                        </td>
                      </tr>

                      {/* Expanded content */}
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={7} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              {/* JSON Schema */}
                              <div>
                                <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                  <Code size={14} />
                                  JSON Схема формы ({template.document_mode_id})
                                </h4>
                                {isLoadingSchema ? (
                                  <div className="flex items-center gap-2 py-4">
                                    <RefreshCw className={`w-4 h-4 animate-spin ${theme.text.muted}`} />
                                    <span className={`text-sm ${theme.text.muted}`}>Загрузка схемы...</span>
                                  </div>
                                ) : schema ? (
                                  <pre className={`text-xs font-mono p-3 rounded-xl max-h-96 overflow-auto whitespace-pre ${
                                    isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'
                                  }`}>
                                    {JSON.stringify(schema, null, 2)}
                                  </pre>
                                ) : (
                                  <p className={`text-sm ${theme.text.muted}`}>Не удалось загрузить схему</p>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer */}
        {!isLoading && sortedTemplates.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>
              Показано {sortedTemplates.length} записей из {total}
            </p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_json_templates</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// CustomsDetail Component
// =============================================================================

interface SimpleDetailProps {
  isDark: boolean;
}

const CustomsDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<CustomsOffice[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90', ghost: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90 shadow-sm', ghost: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCustoms();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncResult(null);
    try {
      const result = await syncCustoms();
      setSyncResult(result);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => { loadData(); }, [loadData]);

  const filteredItems = items.filter(item =>
    (item.short_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
    (item.full_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
    (item.code?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
    (item.kontur_id?.toLowerCase() || '').includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Таможенные органы</h2>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
          <p className={`text-xs font-mono mt-0.5 ${theme.text.muted}`}>GET /common/v1/options/customs</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium ${theme.button.primary}`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Загрузка...' : 'Синхронизировать'}
        </button>
      </div>

      {syncResult && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${syncResult.success ? (isDark ? 'bg-green-500/10 text-green-500' : 'bg-green-50 text-green-700') : (isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700')}`}>
          {syncResult.success ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm">{syncResult.message}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по названию или коду..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных. Нажмите "Синхронизировать"'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">KID</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Краткое название</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Полное название</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr
                        onClick={() => toggleRow(item.id)}
                        className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}
                      >
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-medium ${theme.table.cell}`}>{item.kontur_id}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.short_name || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{item.full_name || '—'}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={4} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${
                                isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'
                              }`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_customs</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// DeclarationTypesDetail Component
// =============================================================================

const DeclarationTypesDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<DeclarationType[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90', ghost: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90 shadow-sm', ghost: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchDeclarationTypes();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncResult(null);
    try {
      const result = await syncDeclarationTypes();
      setSyncResult(result);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Типы деклараций</h2>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
          <p className={`text-xs font-mono mt-0.5 ${theme.text.muted}`}>GET /common/v1/options/declarationTypes</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium ${theme.button.primary}`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Загрузка...' : 'Синхронизировать'}
        </button>
      </div>

      {syncResult && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${syncResult.success ? (isDark ? 'bg-green-500/10 text-green-500' : 'bg-green-50 text-green-700') : (isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700')}`}>
          {syncResult.success ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm">{syncResult.message}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>Нет данных. Нажмите "Синхронизировать"</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">KID</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Описание</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-40">Обновлено</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === items.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr
                        onClick={() => toggleRow(item.id)}
                        className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}
                      >
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.kontur_id}</td>
                        <td className={`py-3 px-4 text-sm font-medium ${theme.table.cell}`}>{item.description}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{formatDate(item.updated_at)}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={4} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${
                                isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'
                              }`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && items.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Всего {total} типов деклараций</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_declaration_types</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// ProceduresDetail Component
// =============================================================================

const ProceduresDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<Procedure[]>([]);
  const [total, setTotal] = useState(0);
  const [uniqueCodes, setUniqueCodes] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [filterTypeId, setFilterTypeId] = useState<number | undefined>(undefined);
  const [declarationTypes, setDeclarationTypes] = useState<DeclarationType[]>([]);

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90', ghost: 'bg-white/5 border-white/10 text-gray-300 hover:bg-white/10' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500',
    select: 'bg-[#1e1e22] border-white/10 text-white'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    button: { primary: 'bg-accent-red text-white hover:bg-accent-red/90 shadow-sm', ghost: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400',
    select: 'bg-gray-50 border-gray-300 text-gray-900'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchProcedures(filterTypeId);
      setItems(data.items);
      setTotal(data.total);
      setUniqueCodes(data.unique_codes);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [filterTypeId]);

  const loadDeclarationTypes = useCallback(async () => {
    try {
      const data = await fetchDeclarationTypes();
      setDeclarationTypes(data.items);
    } catch (err) {
      console.error('Error loading declaration types:', err);
    }
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncResult(null);
    try {
      const result = await syncProcedures();
      setSyncResult(result);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { loadDeclarationTypes(); }, [loadDeclarationTypes]);

  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const getDeclarationTypeName = (typeId: number) => {
    const dtype = declarationTypes.find(dt => dt.kontur_id === typeId);
    return dtype?.description || `Тип ${typeId}`;
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Таможенные процедуры</h2>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей ({uniqueCodes} кодов) {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
          <p className={`text-xs font-mono mt-0.5 ${theme.text.muted}`}>GET /common/v1/options/declarationProcedureTypes</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium ${theme.button.primary}`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Загрузка...' : 'Синхронизировать'}
        </button>
      </div>

      {syncResult && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${syncResult.success ? (isDark ? 'bg-green-500/10 text-green-500' : 'bg-green-50 text-green-700') : (isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700')}`}>
          {syncResult.success ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm">{syncResult.message}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
          <Input placeholder="Поиск по названию или коду..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
        </div>
        <select
          value={filterTypeId ?? ''}
          onChange={(e) => setFilterTypeId(e.target.value ? Number(e.target.value) : undefined)}
          className={`h-10 px-3 rounded-xl border text-sm ${theme.select}`}
        >
          <option value="">Все типы</option>
          {declarationTypes.map(dt => (
            <option key={dt.kontur_id} value={dt.kontur_id}>{dt.description}</option>
          ))}
        </select>
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных. Нажмите "Синхронизировать"'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-16">KID</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-16">DT_ID</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">Тип</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Название процедуры</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr
                        onClick={() => toggleRow(item.id)}
                        className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}
                      >
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.kontur_id}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.declaration_type_id}</td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{getDeclarationTypeName(item.declaration_type_id)}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={6} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${
                                isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'
                              }`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_procedures</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// PackagingGroupsDetail Component (Static)
// =============================================================================

const PackagingGroupsDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<PackagingGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchPackagingGroups();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Группы упаковки</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              Статический
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
      </div>

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>Нет данных</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Название</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === items.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={3} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && items.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Всего {total} записей</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_packaging_groups</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// CurrenciesDetail Component (Static)
// =============================================================================

const CurrenciesDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<Currency[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCurrencies();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.alpha_code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Валюты</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              Статический
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
      </div>

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по коду или названию..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Буквенный</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Название</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.alpha_code}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={4} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_currencies</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// EnterpriseCategoriesDetail Component (Static)
// =============================================================================

const EnterpriseCategoriesDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<EnterpriseCategory[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchEnterpriseCategories();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Категории предприятий</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              Статический
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
      </div>

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по коду или названию..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Название</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={3} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_enterprise_categories</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// MeasurementUnitsDetail Component (Static)
// =============================================================================

const MeasurementUnitsDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<MeasurementUnit[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchMeasurementUnits();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredItems = items.filter(item =>
    item.short_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Единицы измерения</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              Статический
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
      </div>

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по коду или названию..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">Краткое</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Полное название</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.short_name}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.full_name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={4} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_measurement_units</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// DeclarationFeaturesDetail Component (API) - Особенности
// =============================================================================

const DeclarationFeaturesDetail: React.FC<DetailProps> = ({ isDark, onSync }) => {
  const [items, setItems] = useState<DeclarationFeature[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchDeclarationFeatures();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncMessage(null);
    try {
      const result = await syncDeclarationFeatures();
      setSyncMessage(`Синхронизировано: ${result.inserted} добавлено, ${result.updated} обновлено`);
      await loadData();
      onSync?.();
    } catch (err) {
      setError(`Ошибка синхронизации: ${getErrorMessage(err)}`);
    } finally {
      setIsSyncing(false);
    }
  };

  const filteredItems = items.filter(item =>
    item.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Особенности</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono bg-[#6366f1]/15 text-[#6366f1]`}>
              Kontur API
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`h-9 px-4 flex items-center gap-2 rounded-xl text-sm font-medium transition-colors ${theme.button.primary} disabled:opacity-50`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
        </button>
      </div>

      {syncMessage && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-green-500/10 text-green-500' : 'bg-green-50 text-green-700'}`}>
          <CheckCircle className="w-5 h-5" /><span className="text-sm">{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по коду или названию..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Название</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={3} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_declaration_features</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// DocumentTypesDetail Component (Static) - Виды документов
// =============================================================================

const DocumentTypesDetail: React.FC<SimpleDetailProps> = ({ isDark }) => {
  const [items, setItems] = useState<DocumentType[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchDocumentTypes();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredItems = items.filter(item =>
    item.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (item.ed_documents && item.ed_documents.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Виды документов</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-white/10 text-gray-300' : 'bg-gray-100 text-gray-600'}`}>
              Статический
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
      </div>

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по коду, названию или типу ЭД..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-20">Код</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Наименование</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-64">ЭД-документы</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.code}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{item.ed_documents || '—'}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={4} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_document_types</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// CommonOrgsDetail Component (Контрагенты)
// =============================================================================

const CommonOrgsDetail: React.FC<DetailProps> = ({ isDark, onSync }) => {
  const [items, setItems] = useState<CommonOrg[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCommonOrgs();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSync = async () => {
    setIsSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncCommonOrgs();
      setSyncMessage(result.message || `Синхронизировано ${result.total_fetched} контрагентов`);
      await loadData();
      if (onSync) onSync();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  const filteredItems = items.filter(item =>
    (item.org_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
    (item.short_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
    (item.inn?.toLowerCase() || '').includes(searchQuery.toLowerCase())
  );

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) newExpanded.delete(id);
    else newExpanded.add(id);
    setExpandedRows(newExpanded);
  };

  const getOrgTypeLabel = (type: number) => {
    switch (type) {
      case 0: return 'ЮЛ';
      case 1: return 'ИП';
      case 2: return 'ФЛ';
      default: return '—';
    }
  };

  const formatAddress = (address: Record<string, unknown> | null): string => {
    if (!address) return '—';
    const parts: string[] = [];
    if (address.index) parts.push(String(address.index));
    if (address.region) parts.push(String(address.region));
    if (address.city) parts.push(String(address.city));
    if (address.district) parts.push(String(address.district));
    if (address.street) parts.push(String(address.street));
    if (address.house) parts.push(`д. ${address.house}`);
    if (address.building) parts.push(`корп. ${address.building}`);
    if (address.flat) parts.push(`кв. ${address.flat}`);
    if (address.addressText) parts.push(String(address.addressText));
    return parts.length > 0 ? parts.join(', ') : '—';
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Контрагенты</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-indigo-500/20 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
              Kontur API
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${theme.button.primary} disabled:opacity-50`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
        </button>
      </div>

      {syncMessage && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-green-500/10 text-green-400' : 'bg-green-50 text-green-700'}`}>
          <CheckCircle className="w-5 h-5" /><span className="text-sm">{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по названию или ИНН..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных. Синхронизируйте справочник.'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-14">Тип</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">ИНН</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">КПП</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-32">ОГРН</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-52">Название</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Юр. адрес</th>
                  <th className="py-3 px-4 text-center text-xs font-medium uppercase tracking-wider w-16">Ин.</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-xs font-mono ${theme.text.secondary}`}>{getOrgTypeLabel(item.org_type)}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.table.cell}`}>{item.inn || '—'}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.kpp || '—'}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.ogrn || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.short_name || item.org_name || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary} truncate max-w-xs`} title={formatAddress(item.legal_address)}>{formatAddress(item.legal_address)}</td>
                        <td className={`py-3 px-4 text-center text-sm ${theme.text.secondary}`}>
                          {item.is_foreign ? <span className={`px-1.5 py-0.5 rounded text-xs ${isDark ? 'bg-amber-500/20 text-amber-300' : 'bg-amber-100 text-amber-700'}`}>Да</span> : '—'}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={8} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_common_orgs</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// OrganizationsDetail Component (Организации)
// =============================================================================

const OrganizationsDetail: React.FC<DetailProps> = ({ isDark, onSync }) => {
  const [items, setItems] = useState<Organization[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchOrganizations();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSync = async () => {
    setIsSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncOrganizations();
      setSyncMessage(result.message || `Синхронизировано ${result.total_fetched} организаций`);
      await loadData();
      if (onSync) onSync();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) newExpanded.delete(id);
    else newExpanded.add(id);
    setExpandedRows(newExpanded);
  };

  const formatAddress = (address: Record<string, unknown> | null): string => {
    if (!address) return '—';
    const parts: string[] = [];
    if (address.index) parts.push(String(address.index));
    if (address.region) parts.push(String(address.region));
    if (address.city) parts.push(String(address.city));
    if (address.district) parts.push(String(address.district));
    if (address.street) parts.push(String(address.street));
    if (address.house) parts.push(`д. ${address.house}`);
    if (address.building) parts.push(`корп. ${address.building}`);
    if (address.flat) parts.push(`кв. ${address.flat}`);
    return parts.length > 0 ? parts.join(', ') : '—';
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Организации</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-indigo-500/20 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
              Kontur API
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${theme.button.primary} disabled:opacity-50`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
        </button>
      </div>

      {syncMessage && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-green-500/10 text-green-400' : 'bg-green-50 text-green-700'}`}>
          <CheckCircle className="w-5 h-5" /><span className="text-sm">{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>Нет данных. Синхронизируйте справочник.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">ИНН</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-24">КПП</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-32">ОГРН</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-64">Название</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">Адрес</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === items.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-mono font-bold ${theme.table.cell}`}>{item.inn || '—'}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.kpp || '—'}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.ogrn || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.table.cell}`}>{item.name || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary} truncate max-w-xs`} title={formatAddress(item.address)}>{formatAddress(item.address)}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={6} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && items.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Всего {total} организаций</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_organizations</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// EmployeesDetail Component (Подписанты)
// =============================================================================

const EmployeesDetail: React.FC<DetailProps> = ({ isDark, onSync }) => {
  const [items, setItems] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const theme = isDark ? {
    card: 'bg-[#232328] border-white/10',
    text: { primary: 'text-white', secondary: 'text-gray-400', muted: 'text-gray-500' },
    table: { header: 'bg-white/5 border-white/10 text-gray-400', row: 'border-white/10 hover:bg-white/[0.03]', cell: 'text-white' },
    input: 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  } : {
    card: 'bg-white border-gray-300 shadow-sm',
    text: { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-400' },
    table: { header: 'bg-gray-50 border-gray-200 text-gray-500', row: 'border-gray-200 hover:bg-[#f4f4f6]', cell: 'text-gray-900' },
    input: 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400',
    button: { primary: 'bg-[#6366f1] hover:bg-[#4f46e5] text-white' }
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchEmployees();
      setItems(data.items);
      setTotal(data.total);
      setLastUpdated(data.last_updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSync = async () => {
    setIsSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncEmployees();
      setSyncMessage(result.message || `Синхронизировано ${result.total_fetched} подписантов`);
      await loadData();
      if (onSync) onSync();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSyncing(false);
    }
  };

  const filteredItems = items.filter(item => {
    const fullName = [item.surname, item.name, item.patronymic].filter(Boolean).join(' ').toLowerCase();
    return fullName.includes(searchQuery.toLowerCase()) ||
           (item.email?.toLowerCase() || '').includes(searchQuery.toLowerCase());
  });

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) newExpanded.delete(id);
    else newExpanded.add(id);
    setExpandedRows(newExpanded);
  };

  const formatFullName = (item: Employee) => {
    return [item.surname, item.name, item.patronymic].filter(Boolean).join(' ') || '—';
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className={`text-2xl font-bold ${theme.text.primary}`}>Подписанты</h2>
            <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isDark ? 'bg-indigo-500/20 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
              Kontur API
            </span>
          </div>
          <p className={`text-sm ${theme.text.secondary}`}>{total} записей {lastUpdated && <>| Обновлено: {formatDate(lastUpdated)}</>}</p>
        </div>
        <button onClick={handleSync} disabled={isSyncing} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${theme.button.primary} disabled:opacity-50`}>
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
        </button>
      </div>

      {syncMessage && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-green-500/10 text-green-400' : 'bg-green-50 text-green-700'}`}>
          <CheckCircle className="w-5 h-5" /><span className="text-sm">{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'}`}>
          <AlertCircle className="w-5 h-5" /><span className="text-sm">{error}</span>
        </div>
      )}

      <div className="relative">
        <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.text.muted}`} />
        <Input placeholder="Поиск по ФИО или email..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className={`pl-10 h-10 rounded-xl border ${theme.input}`} />
      </div>

      <div className={`rounded-2xl border overflow-hidden ${theme.card}`}>
        {isLoading ? (
          <div className="flex items-center justify-center py-12"><RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} /></div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Database className={`w-12 h-12 mb-3 ${theme.text.muted}`} />
            <p className={`text-sm ${theme.text.secondary}`}>{searchQuery ? 'Ничего не найдено' : 'Нет данных. Синхронизируйте справочник.'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${theme.table.header}`}>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-10"></th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider">ФИО</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-48">Email</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-32">Телефон</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">№ довер.</th>
                  <th className="py-3 px-4 text-left text-xs font-medium uppercase tracking-wider w-28">Дата довер.</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, idx) => {
                  const isExpanded = expandedRows.has(item.id);
                  const isLast = idx === filteredItems.length - 1;
                  return (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => toggleRow(item.id)} className={`cursor-pointer ${!isLast || isExpanded ? `border-b ${theme.table.row}` : theme.table.row}`}>
                        <td className="py-3 px-4">
                          <div className={`w-5 h-5 flex items-center justify-center ${theme.text.muted}`}>
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </div>
                        </td>
                        <td className={`py-3 px-4 text-sm font-medium ${theme.table.cell}`}>{formatFullName(item)}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{item.email || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{item.phone || '—'}</td>
                        <td className={`py-3 px-4 text-sm font-mono ${theme.text.secondary}`}>{item.auth_letter_number || '—'}</td>
                        <td className={`py-3 px-4 text-sm ${theme.text.secondary}`}>{item.auth_letter_date ? formatDate(item.auth_letter_date) : '—'}</td>
                      </tr>
                      {isExpanded && (
                        <tr className={!isLast ? `border-b ${theme.table.row}` : ''}>
                          <td colSpan={6} className="p-0 max-w-0">
                            <div className={`p-4 ${isDark ? 'bg-white/[0.02]' : 'bg-gray-50'}`}>
                              <h4 className={`text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2 ${theme.text.muted}`}>
                                <Code size={14} /> JSON данные
                              </h4>
                              <pre className={`text-xs font-mono p-3 rounded-xl max-h-60 overflow-auto whitespace-pre ${isDark ? 'bg-[#1a1a1e] text-gray-300' : 'bg-white border border-gray-200 text-gray-700'}`}>
                                {JSON.stringify(item, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && filteredItems.length > 0 && (
          <div className={`px-4 py-3 border-t flex items-center justify-between ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <p className={`text-sm ${theme.text.secondary}`}>Показано {filteredItems.length} из {total}</p>
            <p className={`text-xs font-mono ${theme.text.muted}`}>dc_employees</p>
          </div>
        )}
      </div>
    </>
  );
};

// =============================================================================
// ReferencesContent Component
// =============================================================================

const ReferencesContent: React.FC<ReferencesContentProps> = ({
  isDark,
  activeReferenceId,
  onReferenceNavigate
}) => {
  const [references, setReferences] = useState<ReferenceInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use controlled activeReference if provided
  const activeReference = activeReferenceId ?? null;
  const setActiveReference = (id: string | null) => {
    if (onReferenceNavigate) {
      onReferenceNavigate(id);
    }
  };

  const theme = isDark ? {
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
    }
  } : {
    text: {
      primary: 'text-gray-900',
      secondary: 'text-gray-600',
    }
  };

  const loadReferences = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchReferences();
      setReferences(data);
    } catch (err) {
      console.error('Error loading references:', err);
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReferences();
  }, [loadReferences]);

  // Show detail view if reference is selected
  if (activeReference === 'json-templates') {
    return (
      <JsonTemplatesDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'customs') {
    return (
      <CustomsDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'declaration-types') {
    return (
      <DeclarationTypesDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'procedures') {
    return (
      <ProceduresDetail
        isDark={isDark}
      />
    );
  }

  // Static references
  if (activeReference === 'packaging-groups') {
    return (
      <PackagingGroupsDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'currencies') {
    return (
      <CurrenciesDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'enterprise-categories') {
    return (
      <EnterpriseCategoriesDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'measurement-units') {
    return (
      <MeasurementUnitsDetail
        isDark={isDark}
      />
    );
  }

  if (activeReference === 'declaration-features') {
    return (
      <DeclarationFeaturesDetail
        isDark={isDark}
        onSync={loadReferences}
      />
    );
  }

  if (activeReference === 'document-types') {
    return (
      <DocumentTypesDetail
        isDark={isDark}
      />
    );
  }

  // API references - Контрагенты и Подписанты
  if (activeReference === 'common-orgs') {
    return (
      <CommonOrgsDetail
        isDark={isDark}
        onSync={loadReferences}
      />
    );
  }

  if (activeReference === 'organizations') {
    return (
      <OrganizationsDetail
        isDark={isDark}
        onSync={loadReferences}
      />
    );
  }

  if (activeReference === 'employees') {
    return (
      <EmployeesDetail
        isDark={isDark}
        onSync={loadReferences}
      />
    );
  }

  // Main references list
  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${theme.text.primary}`}>
            Справочники
          </h2>
          <p className={`text-sm ${theme.text.secondary}`}>
            Управление справочниками декларанта
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className={`p-3 rounded-xl flex items-center gap-3 ${
          isDark ? 'bg-red-500/10 text-red-500' : 'bg-red-50 text-red-700'
        }`}>
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* References Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className={`w-6 h-6 animate-spin ${theme.text.secondary}`} />
        </div>
      ) : references.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12">
          <Database className={`w-12 h-12 mb-3 ${theme.text.secondary}`} />
          <p className={`text-sm ${theme.text.secondary}`}>
            Нет доступных справочников
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {/* API справочники (слева) */}
          <div className="space-y-4">
            <h3 className={`text-sm font-medium uppercase tracking-wider ${theme.text.muted}`}>
              API справочники
            </h3>
            {references.filter(ref => ref.api_source && !editableReferenceIds.includes(ref.id)).map(ref => (
              <ReferenceCard
                key={ref.id}
                reference={ref}
                isDark={isDark}
                onClick={() => setActiveReference(ref.id)}
              />
            ))}

            {/* Редактируемые справочники (зеленые) - под API справочниками */}
            <h3 className={`text-sm font-medium uppercase tracking-wider pt-4 ${theme.text.muted}`}>
              Редактируемые справочники
            </h3>
            {references.filter(ref => editableReferenceIds.includes(ref.id)).map(ref => (
              <ReferenceCard
                key={ref.id}
                reference={ref}
                isDark={isDark}
                onClick={() => setActiveReference(ref.id)}
              />
            ))}
          </div>
          {/* Статические справочники (справа) */}
          <div className="space-y-4">
            <h3 className={`text-sm font-medium uppercase tracking-wider ${theme.text.muted}`}>
              Статические справочники
            </h3>
            {references.filter(ref => !ref.api_source).map(ref => (
              <ReferenceCard
                key={ref.id}
                reference={ref}
                isDark={isDark}
                onClick={() => setActiveReference(ref.id)}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
};

export default ReferencesContent;
