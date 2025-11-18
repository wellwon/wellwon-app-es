import type { LucideIcon } from 'lucide-react';
import type { ComponentType, LazyExoticComponent } from 'react';

export interface SectionConfig {
  id: string;
  icon: LucideIcon;
  component: LazyExoticComponent<ComponentType<any>> | string;
  requiredRole?: 'admin' | 'user' | 'manager';
  visible?: boolean;
}

export interface SidebarData {
  type?: string;
  title?: string;
  content?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  [key: string]: unknown; // Allow any additional properties
}