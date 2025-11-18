
/**
 * UI Components Barrel Export
 * Централизованный экспорт часто используемых UI компонентов
 */

// Основные компоненты
export { Button } from './button';
export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './card';
export { Input } from './input';
export { Label } from './label';
export { Badge } from './badge';

// Формы
export { Checkbox } from './checkbox';
export { RadioGroup, RadioGroupItem } from './radio-group';
export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
export { Textarea } from './textarea';

// Диалоги и модальные окна
export { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './dialog';
export { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from './sheet';

// Навигация
export { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs';

// Таблицы
export { Table, TableBody, TableCaption, TableCell, TableFooter, TableHead, TableHeader, TableRow } from './table';

// Уведомления - импортируем из правильного местоположения
export { toast, useToast } from '@/hooks/use-toast';
export { Toaster } from './toaster';

// Всплывающие элементы
export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip';
export { Popover, PopoverContent, PopoverTrigger } from './popover';

// Загрузка и состояния
export { Skeleton } from './skeleton';
export { Loader, LoadingScreen } from './loader';
