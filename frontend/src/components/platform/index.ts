// Главный экспорт для всей платформы
export { default as PlatformLayout } from './shared/PlatformLayout';
export { default as ContentRenderer } from './shared/ContentRenderer';
export { default as PlatformSidebar } from './sidebar/PlatformSidebar';
export { platformSections, getSectionById, getSectionComponent } from './shared/SectionConfig';
export type { SectionId, SectionConfig } from './shared/SectionConfig';

// Экспорт всех секций
export * from './sections';