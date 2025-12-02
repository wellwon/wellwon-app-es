// =============================================================================
// Declarant Module - Main Entry Point
// =============================================================================
// Модуль приложения Декларант для Platform Pro
// Содержит страницы, компоненты, типы, API, хуки и сторы

// Pages (for lazy loading in routes)
export * from './pages';

// Components (reusable UI components)
export * from './components';

// Types
export * from './types';

// API
export * from './api';

// Hooks
export { useDeclarant } from './hooks/useDeclarant';

// Stores
export { useDeclarantStore } from './stores/useDeclarantStore';
