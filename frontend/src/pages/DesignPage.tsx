import React, { useState, useEffect } from "react";
import { Palette, Type, Layers, Sparkles, Bell, Check, AlertTriangle, Info, X, Code, Loader2, Play, Pause, Eye, EyeOff, FileText, Calendar, Mail, User, Lock, Search, ChevronDown, ChevronRight, Table as TableIcon, Navigation as NavigationIcon, BarChart3, Filter, MoreHorizontal, Home, Settings, Users, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useToast } from "@/hooks/use-toast";
import Navigation from "@/components/shared/Navigation";
import { GlassCard } from "@/components/design-system/GlassCard";
import { GlassInput } from "@/components/design-system/GlassInput";
import { GlassButton } from "@/components/design-system/GlassButton";
import { FormSection } from "@/components/design-system/FormSection";
const DesignPage = () => {
  const {
    toast
  } = useToast();
  const [activeTab, setActiveTab] = useState("design");
  const [customTabActive, setCustomTabActive] = useState("tab1");
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const showNotification = (type: string) => {
    const notifications = {
      success: {
        title: "Успех!",
        description: "Операция выполнена успешно",
        variant: "success" as const
      },
      error: {
        title: "Ошибка!",
        description: "Что-то пошло не так",
        variant: "error" as const
      },
      warning: {
        title: "Предупреждение!",
        description: "Проверьте введенные данные",
        variant: "warning" as const
      },
      info: {
        title: "Информация",
        description: "Новое уведомление получено",
        variant: "info" as const
      }
    };
    const notification = notifications[type as keyof typeof notifications];
    if (notification) {
      toast(notification);
    }
  };
  const simulateLoading = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 2000);
  };

  // Ripple эффект для кнопок
  const createRipple = (event: React.MouseEvent<HTMLButtonElement>) => {
    const button = event.currentTarget;
    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;
    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${event.clientX - button.offsetLeft - radius}px`;
    circle.style.top = `${event.clientY - button.offsetTop - radius}px`;
    circle.classList.add('ripple-effect');
    circle.style.position = 'absolute';
    circle.style.borderRadius = '50%';
    circle.style.background = 'rgba(255, 255, 255, 0.3)';
    circle.style.transform = 'scale(0)';
    circle.style.animation = 'ripple-animation 0.6s linear';
    circle.style.pointerEvents = 'none';
    const ripple = button.getElementsByClassName('ripple-effect')[0];
    if (ripple) {
      ripple.remove();
    }
    button.appendChild(circle);
    setTimeout(() => {
      circle.remove();
    }, 600);
  };

  // Анимация прогресс баров при загрузке
  useEffect(() => {
    const timer = setTimeout(() => {
      document.querySelectorAll('.progress-bar').forEach(bar => {
        const width = (bar as HTMLElement).style.width;
        (bar as HTMLElement).style.width = '0%';
        setTimeout(() => {
          (bar as HTMLElement).style.width = width;
        }, 100);
      });
    }, 500);
    return () => clearTimeout(timer);
  }, []);
  return <div className="min-h-screen bg-dark-gray pt-24">
      <Navigation />

      <div className="container mx-auto px-6 py-12">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-6xl font-black text-white mb-6">
            Design System
          </h1>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Современная дизайн-система с iOS Glass Effect для создания красивых веб-приложений
          </p>
        </div>

        {/* Main Tabs */}
        <Tabs defaultValue="design" className="space-y-8">
          <TabsList className="grid w-full grid-cols-8 gap-2 bg-medium-gray/30 p-2 rounded-2xl backdrop-blur-sm border border-white/10">
            <TabsTrigger value="design" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <Palette className="w-4 h-4" />
              Дизайн
            </TabsTrigger>
            <TabsTrigger value="components" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <Layers className="w-4 h-4" />
              Компоненты
            </TabsTrigger>
            <TabsTrigger value="notifications" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <Bell className="w-4 h-4" />
              Уведомления
            </TabsTrigger>
            <TabsTrigger value="interactive" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <Play className="w-4 h-4" />
              Интерактивность
            </TabsTrigger>
            <TabsTrigger value="animations" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <Sparkles className="w-4 h-4" />
              Анимации
            </TabsTrigger>
            <TabsTrigger value="tables" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300 text-center">
              <TableIcon className="w-4 h-4" />
              Таблицы
            </TabsTrigger>
            <TabsTrigger value="navigation" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <NavigationIcon className="w-4 h-4" />
              Навигация
            </TabsTrigger>
            <TabsTrigger value="forms" className="glass-card flex items-center gap-2 px-4 py-3 text-gray-400 hover:text-white data-[state=active]:text-white data-[state=active]:bg-accent-red data-[state=active]:border-accent-red rounded-xl transition-all duration-300">
              <FileText className="w-4 h-4" />
              Формы
            </TabsTrigger>
          </TabsList>

          {/* Design Tab (Colors + Typography + CSS Variables) */}
          <TabsContent value="design" className="space-y-8">
            {/* Colors and Typography */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Цветовая палитра и типографика</CardTitle>
                <CardDescription>
                  Основные элементы дизайн-системы: цвета, шрифты и переменные
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Color Palette */}
                <div>
                  <h3 className="text-xl font-bold text-white mb-6">Цвета</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="space-y-3">
                      <div className="w-full h-24 rounded-xl shadow-lg flex items-end p-4 text-white font-medium text-sm bg-accent-red">
                        #ea3857
                      </div>
                      <div>
                        <h4 className="font-semibold text-white">Accent Red</h4>
                        <p className="text-sm text-gray-400">var(--accent-red)</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="w-full h-24 rounded-xl shadow-lg flex items-end p-4 text-white font-medium text-sm bg-dark-gray border border-white/10">
                        #1a1a1d
                      </div>
                      <div>
                        <h4 className="font-semibold text-white">Dark Gray</h4>
                        <p className="text-sm text-gray-400">var(--dark-gray)</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="w-full h-24 rounded-xl shadow-lg flex items-end p-4 text-white font-medium text-sm bg-medium-gray border border-white/10">
                        #232328
                      </div>
                      <div>
                        <h4 className="font-semibold text-white">Medium Gray</h4>
                        <p className="text-sm text-gray-400">var(--medium-gray)</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="w-full h-24 rounded-xl shadow-lg flex items-end p-4 text-white font-medium text-sm border border-white/10" style={{
                      backgroundColor: '#2c2c33'
                    }}>
                        #2c2c33
                      </div>
                      <div>
                        <h4 className="font-semibold text-white">Light Gray</h4>
                        <p className="text-sm text-gray-400">Границы и акценты</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Typography */}
                <div className="p-6 border border-white/10 rounded-2xl bg-medium-gray/20">
                  <h3 className="text-xl font-bold text-white mb-6">Типографика</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div className="space-y-4">
                      <h1 className="text-5xl font-black text-white">Заголовок H1</h1>
                      <h2 className="text-4xl font-extrabold text-white">Заголовок H2</h2>
                      <h3 className="text-3xl font-bold text-white">Заголовок H3</h3>
                      <h4 className="text-2xl font-semibold text-white">Заголовок H4</h4>
                      <h5 className="text-xl font-medium text-white">Заголовок H5</h5>
                      <h6 className="text-lg font-medium text-white">Заголовок H6</h6>
                    </div>
                    <div className="space-y-4">
                      <p className="text-xl text-white">Большой текст (text-xl)</p>
                      <p className="text-lg text-white">Средний текст (text-lg)</p>
                      <p className="text-base text-white">Базовый текст (text-base)</p>
                      <p className="text-sm text-gray-300">Маленький текст (text-sm)</p>
                      <p className="text-xs text-gray-400">Очень маленький (text-xs)</p>
                      <p className="text-lg text-accent-red font-semibold">Акцентный текст</p>
                    </div>
                  </div>
                </div>

                {/* CSS Variables */}
                <div>
                  <h3 className="text-xl font-bold text-white mb-6">CSS Переменные</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="bg-medium-gray/50">
                      <CardHeader>
                        <CardTitle className="text-white text-lg">Цвета</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2 font-mono text-sm">
                        <div className="flex justify-between text-gray-300">
                          <span>--accent-red:</span>
                          <span className="text-accent-red">#ea3857</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--dark-gray:</span>
                          <span>#1a1a1d</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--medium-gray:</span>
                          <span>#232328</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--text-white:</span>
                          <span className="text-white">#ffffff</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--text-gray-400:</span>
                          <span className="text-gray-400">#9ca3af</span>
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card className="bg-medium-gray/50">
                      <CardHeader>
                        <CardTitle className="text-white text-lg">Эффекты</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2 font-mono text-sm">
                        <div className="flex justify-between text-gray-300">
                          <span>--glass-backdrop:</span>
                          <span>blur(12px)</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--radius-lg:</span>
                          <span>16px</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--spacing:</span>
                          <span>16px</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--spacing-lg:</span>
                          <span>24px</span>
                        </div>
                        <div className="flex justify-between text-gray-300">
                          <span>--transition-smooth:</span>
                          <span>all 0.3s ease</span>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Components Tab */}
          <TabsContent value="components" className="space-y-8">
            {/* Buttons */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Кнопки</CardTitle>
                <CardDescription>
                  Различные варианты кнопок с glass эффектами
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="space-y-4">
                    <h4 className="font-semibold text-white">Варианты стилей</h4>
                    <div className="flex flex-wrap gap-4">
                      <Button variant="accent">Primary</Button>
                      <Button variant="secondary">Secondary</Button>
                      <Button variant="outline">Outline</Button>
                      <Button variant="ghost">Ghost</Button>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <h4 className="font-semibold text-white">Размеры</h4>
                    <div className="flex flex-wrap items-center gap-4">
                      <Button variant="accent" size="sm">Small</Button>
                      <Button variant="accent" size="default">Default</Button>
                      <Button variant="accent" size="lg">Large</Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Cards */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Карточки (Glass Cards)</CardTitle>
                <CardDescription>
                  Карточки с различными стилями и эффектами стекла
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Default Glass Card */}
                  <div className="glass-card bg-medium-gray/60 border border-white/10 backdrop-blur-sm p-6 rounded-xl">
                    <h4 className="text-lg font-semibold text-white mb-2">Базовая карточка</h4>
                    <p className="text-gray-400 text-sm mb-4">
                      Стандартная карточка с glass эффектом
                    </p>
                    <Button variant="accent" size="sm">Действие</Button>
                  </div>

                  {/* Accent Glass Card */}
                  <div className="glass-card bg-accent-red/10 border border-accent-red/30 backdrop-blur-sm p-6 rounded-xl">
                    <h4 className="text-lg font-semibold text-white mb-2">Акцентная карточка</h4>
                    <p className="text-gray-400 text-sm mb-4">
                      Карточка с акцентным стилем
                    </p>
                    <Button variant="secondary" size="sm">Подробнее</Button>
                  </div>

                  {/* Elevated Glass Card */}
                  <div className="glass-card bg-medium-gray/80 border border-white/20 backdrop-blur-sm p-6 rounded-xl shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
                    <h4 className="text-lg font-semibold text-white mb-2">Приподнятая карточка</h4>
                    <p className="text-gray-400 text-sm mb-4">
                      Карточка с тенью и hover эффектом
                    </p>
                    <Button variant="outline" size="sm">Открыть</Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Modal Example */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Модальные окна</CardTitle>
                <CardDescription>
                  Диалоги и всплывающие окна с glass эффектом
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                    <DialogTrigger asChild>
                      <Button variant="accent">Открыть модальное окно</Button>
                    </DialogTrigger>
                    <DialogContent className="bg-medium-gray/90 backdrop-blur-md border border-white/20">
                      <DialogHeader>
                        <DialogTitle className="text-white">Пример модального окна</DialogTitle>
                        <DialogDescription className="text-gray-400">
                          Это модальное окно с glass эффектом и размытием фона
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <p className="text-gray-300">
                          Содержимое модального окна с красивым дизайном в стиле WellWon.
                        </p>
                      </div>
                      <div className="flex justify-end gap-3">
                        <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
                          Отмена
                        </Button>
                        <Button variant="accent" onClick={() => setIsModalOpen(false)}>
                          Подтвердить
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardContent>
            </Card>

          </TabsContent>

          {/* Notifications Tab */}
          <TabsContent value="notifications" className="space-y-8">
            {/* Notification Cards */}
            <Card>
              <CardHeader>
                <CardTitle style={{
                color: "#ea3857"
              }}>Уведомления</CardTitle>
                <CardDescription>
                  Примеры различных типов уведомлений и сообщений состояния
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Success Notification */}
                  <Card style={{
                  borderColor: "rgba(34, 197, 94, 0.2)",
                  backgroundColor: "rgba(34, 197, 94, 0.05)"
                }}>
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3 mb-3">
                        <Check className="w-5 h-5" style={{
                        color: "#22c55e"
                      }} />
                        <h4 className="font-semibold text-white">Успех</h4>
                      </div>
                      <p className="text-gray-300 mb-4">
                        Операция выполнена успешно. Данные сохранены.
                      </p>
                      <Button variant="accent" size="sm" onClick={() => showNotification('success')} style={{
                      backgroundColor: "#22c55e",
                      borderColor: "#22c55e"
                    }} className="hover:bg-green-600">
                        Показать уведомление
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Error Notification */}
                  <Card style={{
                  borderColor: "rgba(234, 56, 87, 0.2)",
                  backgroundColor: "rgba(234, 56, 87, 0.05)"
                }}>
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3 mb-3">
                        <X className="w-5 h-5" style={{
                        color: "#ea3857"
                      }} />
                        <h4 className="font-semibold text-white">Ошибка</h4>
                      </div>
                      <p className="text-gray-300 mb-4">
                        Произошла ошибка при выполнении операции.
                      </p>
                      <Button variant="accent" size="sm" onClick={() => showNotification('error')} style={{
                      backgroundColor: "#ea3857",
                      borderColor: "#ea3857"
                    }} className="hover:bg-accent-red-dark">
                        Показать уведомление
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Warning Notification */}
                  <Card style={{
                  borderColor: "rgba(234, 179, 8, 0.2)",
                  backgroundColor: "rgba(234, 179, 8, 0.05)"
                }}>
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3 mb-3">
                        <AlertTriangle className="w-5 h-5" style={{
                        color: "#eab308"
                      }} />
                        <h4 className="font-semibold text-white">Предупреждение</h4>
                      </div>
                      <p className="text-gray-300 mb-4">
                        Проверьте правильность введенных данных.
                      </p>
                      <Button variant="accent" size="sm" onClick={() => showNotification('warning')} style={{
                      backgroundColor: "#eab308",
                      borderColor: "#eab308"
                    }} className="hover:bg-yellow-600 text-black">
                        Показать уведомление
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Info Notification */}
                  <Card style={{
                  borderColor: "rgba(59, 130, 246, 0.2)",
                  backgroundColor: "rgba(59, 130, 246, 0.05)"
                }}>
                    <CardContent className="pt-6">
                      <div className="flex items-center gap-3 mb-3">
                        <Info className="w-5 h-5" style={{
                        color: "#3b82f6"
                      }} />
                        <h4 className="font-semibold text-white">Информация</h4>
                      </div>
                      <p className="text-gray-300 mb-4">
                        Новая информация доступна для просмотра.
                      </p>
                      <Button variant="accent" size="sm" onClick={() => showNotification('info')} style={{
                      backgroundColor: "#3b82f6",
                      borderColor: "#3b82f6"
                    }} className="hover:bg-gray-600">
                        Показать уведомление
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </CardContent>
            </Card>

            {/* Error States */}
            <Card>
              <CardHeader>
              <CardTitle style={{
                color: "#ea3857"
              }}>Страницы ошибок и состояния</CardTitle>
                <CardDescription>
                  Различные состояния ошибок и их отображение
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 404 Error */}
                <Card style={{
                borderColor: "rgba(234, 56, 87, 0.2)",
                backgroundColor: "rgba(234, 56, 87, 0.05)"
              }}>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="w-5 h-5" style={{
                      color: "#ea3857"
                    }} />
                      <CardTitle className="text-white">404 - Страница не найдена</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="text-center py-8">
                    <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{
                    backgroundColor: "#ea3857"
                  }}>
                      <AlertTriangle className="w-10 h-10 text-white" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-4">Страница не найдена</h2>
                    <p className="text-gray-300 mb-6 max-w-md mx-auto">
                      Запрашиваемая страница не существует или была перемещена.
                    </p>
                    <div className="flex gap-4 justify-center">
                      <Button variant="secondary">Назад</Button>
                      <Button variant="accent" style={{
                      backgroundColor: "#ea3857",
                      borderColor: "#ea3857"
                    }}>На главную</Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Server Error */}
                <Card style={{
                borderColor: "rgba(234, 56, 87, 0.2)",
                backgroundColor: "rgba(234, 56, 87, 0.05)"
              }}>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <X className="w-5 h-5" style={{
                      color: "#ea3857"
                    }} />
                      <CardTitle className="text-white">500 - Ошибка сервера</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="text-center py-8">
                    <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{
                    backgroundColor: "#ea3857"
                  }}>
                      <X className="w-10 h-10 text-white" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-4">Что-то пошло не так</h2>
                    <p className="text-gray-300 mb-6 max-w-md mx-auto">
                      Произошла ошибка при загрузке страницы.
                    </p>
                    <Button variant="accent" style={{
                    backgroundColor: "#ea3857",
                    borderColor: "#ea3857"
                  }} onClick={() => {
                    // Показываем уведомление вместо перезагрузки
                    toast({
                      title: "Страница обновлена",
                      description: "Состояние компонентов сброшено",
                      variant: "success"
                    });
                    // Можно добавить логику сброса состояния компонентов
                  }}>
                       Сбросить состояние
                     </Button>
                  </CardContent>
                </Card>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Interactive Tab */}
          <TabsContent value="interactive" className="space-y-8">
            {/* Custom Tabs */}
            <Card>
              <CardHeader>
                <CardTitle style={{
                color: "#ea3857"
              }}>Кастомные табы</CardTitle>
                <CardDescription>
                  Минималистичные табы с красным подчеркиванием активного таба
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="max-w-2xl mx-auto">
                  <div className="flex border-b border-white/10 mb-6">
                    {["tab1", "tab2", "tab3"].map(tab => <button key={tab} onClick={() => setCustomTabActive(tab)} className={`px-6 py-3 text-sm font-medium transition-all duration-300 border-b-2 ${customTabActive === tab ? "text-white border-b-2" : "text-gray-400 hover:text-white border-transparent"}`} style={{
                    borderBottomColor: customTabActive === tab ? "#ea3857" : "transparent"
                  }}>
                        {tab === "tab1" && "Первый"}
                        {tab === "tab2" && "Второй"}
                        {tab === "tab3" && "Третий"}
                      </button>)}
                  </div>
                  <div className="min-h-[120px]">
                    {customTabActive === "tab1" && <div className="animate-fade-in">
                        <h3 className="text-xl font-semibold text-white mb-3">Первый таб</h3>
                        <p className="text-gray-300">Контент первого таба с плавной анимацией появления.</p>
                      </div>}
                    {customTabActive === "tab2" && <div className="animate-fade-in">
                        <h3 className="text-xl font-semibold text-white mb-3">Второй таб</h3>
                        <p className="text-gray-300">Здесь находится содержимое второго таба.</p>
                      </div>}
                    {customTabActive === "tab3" && <div className="animate-fade-in">
                        <h3 className="text-xl font-semibold text-white mb-3">Третий таб</h3>
                        <p className="text-gray-300">И это контент третьего таба с красивыми переходами.</p>
                      </div>}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Interactive Effects */}
            <Card>
              <CardHeader>
                <CardTitle style={{
                color: "#ea3857"
              }}>Интерактивные эффекты</CardTitle>
                <CardDescription>
                  Интерактивные кнопки с различными эффектами и анимациями
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <button className="btn btn-primary ripple hover-lift tooltip relative overflow-hidden" data-tooltip="Эффект поднятия" onClick={createRipple} style={{
                  padding: "12px 24px",
                  borderRadius: "12px",
                  backgroundColor: "#ea3857",
                  color: "white",
                  border: "none",
                  cursor: "pointer",
                  position: "relative"
                }}>
                    Hover Lift
                  </button>
                  <button className="btn btn-secondary ripple hover-scale tooltip relative overflow-hidden" data-tooltip="Эффект масштабирования" onClick={createRipple} style={{
                  padding: "12px 24px",
                  borderRadius: "12px",
                  backgroundColor: "hsl(240 6% 20%)",
                  color: "hsl(214 15% 82%)",
                  border: "1px solid hsl(240 6% 20%)",
                  cursor: "pointer",
                  position: "relative"
                }}>
                    Hover Scale
                  </button>
                  <button className="btn btn-outline ripple hover-glow tooltip relative overflow-hidden" data-tooltip="Эффект свечения" onClick={createRipple} style={{
                  padding: "12px 24px",
                  borderRadius: "12px",
                  backgroundColor: "transparent",
                  color: "#ea3857",
                  border: "2px solid #ea3857",
                  cursor: "pointer",
                  position: "relative"
                }}>
                    Hover Glow
                  </button>
                  <button className="btn btn-ghost ripple animate-float tooltip relative overflow-hidden" data-tooltip="Эффект плавания" onClick={createRipple} style={{
                  padding: "12px 24px",
                  borderRadius: "12px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  color: "#d1d5db",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  cursor: "pointer",
                  position: "relative"
                }}>
                    Float Animation
                  </button>
                </div>
              </CardContent>
            </Card>

          </TabsContent>

          {/* Animations Tab */}
          <TabsContent value="animations" className="space-y-8">
            {/* Loading States */}
            <Card>
              <CardHeader>
                <CardTitle style={{
                color: "#ea3857"
              }}>Loading состояния</CardTitle>
                <CardDescription>
                  Различные виды индикаторов загрузки с новыми эффектами
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <Card className="text-center">
                    <CardContent className="pt-6">
                      <h5 className="text-white font-semibold mb-4">Spinner</h5>
                      <div className="loading-spinner mx-auto mb-4"></div>
                      <p className="text-gray-400 text-sm">Основной спиннер</p>
                    </CardContent>
                  </Card>
                  
                  <Card className="text-center">
                    <CardContent className="pt-6">
                      <h5 className="text-white font-semibold mb-4">Dots</h5>
                      <div className="loading-dots justify-center mb-4">
                        <div className="loading-dot"></div>
                        <div className="loading-dot"></div>
                        <div className="loading-dot"></div>
                      </div>
                      <p className="text-gray-400 text-sm">Анимированные точки</p>
                    </CardContent>
                  </Card>
                  
                  <Card className="text-center">
                    <CardContent className="pt-6">
                      <h5 className="text-white font-semibold mb-4">Pulse</h5>
                      <Button variant="accent" className="animate-pulse mb-4" style={{
                      backgroundColor: "#ea3857"
                    }}>
                        Loading...
                      </Button>
                      <p className="text-gray-400 text-sm">Пульсирующая кнопка</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Progress Bars */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-white">Progress Bars</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm text-gray-300 mb-2">
                        <span>Загрузка файлов</span>
                        <span>75%</span>
                      </div>
                      <div className="progress">
                        <div className="progress-bar" style={{
                        width: "75%"
                      }}></div>
                      </div>
                    </div>
                    
                    <div>
                      <div className="flex justify-between text-sm text-gray-300 mb-2">
                        <span>Обработка данных</span>
                        <span>45%</span>
                      </div>
                      <div className="progress">
                        <div className="progress-bar" style={{
                        width: "45%"
                      }}></div>
                      </div>
                    </div>
                    
                    <div>
                      <div className="flex justify-between text-sm text-gray-300 mb-2">
                        <span>Синхронизация</span>
                        <span>90%</span>
                      </div>
                      <div className="progress">
                        <div className="progress-bar" style={{
                        width: "90%"
                      }}></div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </CardContent>
            </Card>

            {/* Interactive Effects */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Интерактивные эффекты</CardTitle>
                <CardDescription>
                  Hover эффекты и анимации взаимодействия
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  <Card className="hover:-translate-y-2 hover:shadow-2xl hover:shadow-accent-red/20 transition-all duration-300 cursor-pointer">
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Lift Effect</h4>
                      <p className="text-gray-300">Наведите курсор для подъёма</p>
                    </CardContent>
                  </Card>

                  <Card className="hover:scale-105 transition-transform duration-300 cursor-pointer">
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Scale Effect</h4>
                      <p className="text-gray-300">Увеличение при наведении</p>
                    </CardContent>
                  </Card>

                  <Card className="hover:bg-gradient-to-br hover:from-accent-red/10 hover:to-accent-red/5 transition-all duration-300 cursor-pointer">
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Glow Effect</h4>
                      <p className="text-gray-300">Свечение при взаимодействии</p>
                    </CardContent>
                  </Card>

                  <Card className="animate-bounce cursor-pointer">
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Bounce</h4>
                      <p className="text-gray-300">Постоянная bounce анимация</p>
                    </CardContent>
                  </Card>

                  <Card className="hover:animate-pulse transition-all duration-300 cursor-pointer">
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Pulse on Hover</h4>
                      <p className="text-gray-300">Pulse эффект при наведении</p>
                    </CardContent>
                  </Card>

                  <Card className="animate-pulse animate-fade-in cursor-pointer" style={{
                  animationDuration: '3s'
                }}>
                    <CardContent className="pt-6">
                      <h4 className="text-lg font-semibold text-white mb-2">Float Effect</h4>
                      <p className="text-gray-300">Плавающая анимация</p>
                    </CardContent>
                  </Card>
                </div>
              </CardContent>
            </Card>

            {/* Button Animations */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Анимации кнопок</CardTitle>
                <CardDescription>
                  Интерактивные кнопки с различными эффектами
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4">
                  <Button variant="accent" className="hover:shadow-lg hover:shadow-accent-red/30 transition-all duration-300">
                    Shadow Effect
                  </Button>
                  <Button variant="outline" className="hover:bg-accent-red hover:text-white hover:border-accent-red transition-all duration-300">
                    Fill Effect
                  </Button>
                  <Button variant="ghost" className="hover:bg-accent-red/10 hover:scale-105 transition-all duration-300">
                    Scale & Color
                  </Button>
                  <Button variant="secondary" onClick={() => setIsPlaying(!isPlaying)} className="hover:bg-accent-red hover:text-white transition-all duration-300">
                    {isPlaying ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                    {isPlaying ? 'Pause' : 'Play'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tables Tab */}
          <TabsContent value="tables" className="space-y-8">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <TableIcon className="w-5 h-5 text-accent-red" />
                  Таблицы и отображение данных
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Компоненты для структурированного отображения данных
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Data Table */}
                

                {/* Stats Cards */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">Карточки статистики</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card className="glass-card border-gray-500/20">
                      <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-gray-500/20 rounded-lg">
                            <Users className="w-6 h-6 text-gray-400" />
                          </div>
                          <div>
                            <p className="text-sm text-gray-400">Пользователи</p>
                            <p className="text-2xl font-bold text-white">2,543</p>
                            <p className="text-xs text-gray-400">+12.5% за месяц</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card className="glass-card border-green-500/20">
                      <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-green-500/20 rounded-lg">
                            <BarChart3 className="w-6 h-6 text-green-400" />
                          </div>
                          <div>
                            <p className="text-sm text-gray-400">Продажи</p>
                            <p className="text-2xl font-bold text-white">$45,231</p>
                            <p className="text-xs text-green-400">+8.2% за неделю</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card className="glass-card border-accent-red/20">
                      <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-accent-red/20 rounded-lg">
                            <Settings className="w-6 h-6 text-accent-red" />
                          </div>
                          <div>
                            <p className="text-sm text-gray-400">Активность</p>
                            <p className="text-2xl font-bold text-white">89.3%</p>
                            <p className="text-xs text-[#ea3857]">-2.1% за день</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                   </div>
                 </div>

                 {/* Продвинутая таблица заказов */}
                 <div>
                   <h3 className="text-lg font-semibold text-white mb-4">Управление заказами</h3>
                   <div className="rounded-xl border border-white/10 overflow-hidden">
                     <Table>
                       <TableHeader>
                         <TableRow className="bg-light-gray border-white/10">
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">
                             <Checkbox className="border-white/20" />
                           </TableHead>
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">Заказ</TableHead>
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">Клиент</TableHead>
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">Сумма</TableHead>
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">Статус</TableHead>
                           <TableHead className="text-gray-300 font-medium bg-[#3a3a3f]">Дата</TableHead>
                           <TableHead className="text-gray-300 font-medium text-right bg-[#3a3a3f]">Действия</TableHead>
                         </TableRow>
                       </TableHeader>
                       <TableBody>
                         <TableRow className="border-white/10 hover:bg-light-gray/40 transition-colors">
                           <TableCell className="p-4">
                             <Checkbox className="border-white/20" />
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-10 h-10 rounded-lg bg-accent-red/20 flex items-center justify-center">
                                 <span className="text-accent-red font-bold text-sm">#1001</span>
                               </div>
                               <div>
                                 <span className="text-white font-medium">Логистические услуги</span>
                                 <p className="text-xs text-gray-400">Международные перевозки</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                                 <User className="w-4 h-4 text-blue-400" />
                               </div>
                               <div>
                                 <span className="text-white font-medium">ООО "Глобал Трейд"</span>
                                 <p className="text-xs text-gray-400">globaltrade@example.com</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <span className="text-white font-bold text-lg">$25,840</span>
                           </TableCell>
                           <TableCell className="p-4">
                             <Badge variant="secondary" className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                               В обработке
                             </Badge>
                           </TableCell>
                           <TableCell className="p-4 text-gray-400">15.01.2024</TableCell>
                           <TableCell className="p-4 text-right">
                             <div className="flex items-center justify-end gap-2">
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Eye className="w-4 h-4" />
                               </Button>
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Settings className="w-4 h-4" />
                               </Button>
                               <Button variant="destructive" size="sm" className="hover:scale-105 transition-transform">
                                 <Trash2 className="w-4 h-4" />
                               </Button>
                             </div>
                           </TableCell>
                         </TableRow>
                         
                         <TableRow className="border-white/10 hover:bg-light-gray/40 transition-colors">
                           <TableCell className="p-4">
                             <Checkbox className="border-white/20" />
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-10 h-10 rounded-lg bg-accent-red/20 flex items-center justify-center">
                                 <span className="text-accent-red font-bold text-sm">#1002</span>
                               </div>
                               <div>
                                 <span className="text-white font-medium">Морские перевозки</span>
                                 <p className="text-xs text-gray-400">Контейнерные грузы</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                                 <User className="w-4 h-4 text-green-400" />
                               </div>
                               <div>
                                 <span className="text-white font-medium">ЗАО "Океан Лоджистик"</span>
                                 <p className="text-xs text-gray-400">ocean@example.com</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <span className="text-white font-bold text-lg">$48,200</span>
                           </TableCell>
                           <TableCell className="p-4">
                             <Badge variant="secondary" className="bg-green-500/20 text-green-400 border-green-500/30">
                               Выполнен
                             </Badge>
                           </TableCell>
                           <TableCell className="p-4 text-gray-400">12.01.2024</TableCell>
                           <TableCell className="p-4 text-right">
                             <div className="flex items-center justify-end gap-2">
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Eye className="w-4 h-4" />
                               </Button>
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Settings className="w-4 h-4" />
                               </Button>
                               <Button variant="destructive" size="sm" className="hover:scale-105 transition-transform">
                                 <Trash2 className="w-4 h-4" />
                               </Button>
                             </div>
                           </TableCell>
                         </TableRow>

                         <TableRow className="border-white/10 hover:bg-light-gray/40 transition-colors">
                           <TableCell className="p-4">
                             <Checkbox className="border-white/20" />
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-10 h-10 rounded-lg bg-accent-red/20 flex items-center justify-center">
                                 <span className="text-accent-red font-bold text-sm">#1003</span>
                               </div>
                               <div>
                                 <span className="text-white font-medium">Авиаперевозки</span>
                                 <p className="text-xs text-gray-400">Срочная доставка</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <div className="flex items-center gap-3">
                               <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center">
                                 <User className="w-4 h-4 text-orange-400" />
                               </div>
                               <div>
                                 <span className="text-white font-medium">ИП Быстров А.С.</span>
                                 <p className="text-xs text-gray-400">fast@example.com</p>
                               </div>
                             </div>
                           </TableCell>
                           <TableCell className="p-4">
                             <span className="text-white font-bold text-lg">$15,690</span>
                           </TableCell>
                           <TableCell className="p-4">
                             <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                               Ожидание
                             </Badge>
                           </TableCell>
                           <TableCell className="p-4 text-gray-400">10.01.2024</TableCell>
                           <TableCell className="p-4 text-right">
                             <div className="flex items-center justify-end gap-2">
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Eye className="w-4 h-4" />
                               </Button>
                               <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-light-gray/50">
                                 <Settings className="w-4 h-4" />
                               </Button>
                               <Button variant="destructive" size="sm" className="hover:scale-105 transition-transform">
                                 <Trash2 className="w-4 h-4" />
                               </Button>
                             </div>
                           </TableCell>
                         </TableRow>
                       </TableBody>
                     </Table>
                   </div>
                   
                   {/* Действия с таблицей */}
                   <div className="flex items-center justify-between mt-4 p-4 bg-medium-gray/20 rounded-xl border border-white/10">
                     <div className="flex items-center gap-4">
                       <span className="text-sm text-gray-400">3 из 25 выбрано</span>
                       <div className="flex items-center gap-2">
                         <Button variant="secondary" size="sm" className="hover:bg-accent-red hover:text-white transition-colors">
                           <Filter className="w-4 h-4 mr-2" />
                           Фильтр
                         </Button>
                         <Button variant="secondary" size="sm" className="hover:bg-accent-red hover:text-white transition-colors">
                           Экспорт
                         </Button>
                       </div>
                     </div>
                     <div className="flex items-center gap-2">
                       <Button variant="accent" size="sm" className="hover:shadow-lg hover:shadow-accent-red/30">
                         Создать заказ
                       </Button>
                     </div>
                   </div>
                 </div>
               </CardContent>
             </Card>
           </TabsContent>

          {/* Navigation Tab */}
          <TabsContent value="navigation" className="space-y-8">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <NavigationIcon className="w-5 h-5 text-accent-red" />
                  Навигация и структура
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Компоненты для навигации по приложению
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Breadcrumbs */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">Хлебные крошки</h3>
                  <div className="p-4 bg-medium-gray/20 rounded-xl border border-white/10">
                    <nav className="flex items-center space-x-2 text-sm">
                      <button className="text-gray-400 hover:text-white transition-colors">
                        <Home className="w-4 h-4" />
                      </button>
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                      <button className="text-gray-400 hover:text-white transition-colors">
                        Проекты
                      </button>
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                      <button className="text-gray-400 hover:text-white transition-colors">
                        WellWon
                      </button>
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                      <span className="text-white font-medium">
                        Дизайн-система
                      </span>
                    </nav>
                  </div>
                </div>

                {/* Pagination */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">Пагинация</h3>
                  <div className="p-4 bg-medium-gray/20 rounded-xl border border-white/10">
                    <Pagination>
                      <PaginationContent>
                        <PaginationItem>
                          <PaginationPrevious href="#" className="text-gray-400 hover:text-white border-white/10 hover:bg-accent-red/20" />
                        </PaginationItem>
                        <PaginationItem>
                          <PaginationLink href="#" className="text-gray-400 hover:text-white border-white/10 hover:bg-accent-red/20">1</PaginationLink>
                        </PaginationItem>
                        <PaginationItem>
                          <PaginationLink href="#" isActive className="bg-accent-red text-white border-accent-red">2</PaginationLink>
                        </PaginationItem>
                        <PaginationItem>
                          <PaginationLink href="#" className="text-gray-400 hover:text-white border-white/10 hover:bg-accent-red/20">3</PaginationLink>
                        </PaginationItem>
                        <PaginationItem>
                          <PaginationNext href="#" className="text-gray-400 hover:text-white border-white/10 hover:bg-accent-red/20" />
                        </PaginationItem>
                      </PaginationContent>
                    </Pagination>
                  </div>
                </div>

                {/* Navigation Menu */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">Навигационное меню</h3>
                  <div className="p-4 bg-medium-gray/20 rounded-xl border border-white/10">
                    <nav className="flex items-center space-x-6">
                      <a href="#" className="text-white font-medium border-b-2 border-accent-red pb-2">
                        Главная
                      </a>
                      <a href="#" className="text-gray-400 hover:text-white pb-2 border-b-2 border-transparent hover:border-gray-600 transition-all">
                        О нас
                      </a>
                      <a href="#" className="text-gray-400 hover:text-white pb-2 border-b-2 border-transparent hover:border-gray-600 transition-all">
                        Услуги
                      </a>
                      <a href="#" className="text-gray-400 hover:text-white pb-2 border-b-2 border-transparent hover:border-gray-600 transition-all">
                        Контакты
                      </a>
                    </nav>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Forms Tab */}
          <TabsContent value="forms" className="space-y-8">
            {/* Базовые элементы */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Базовые элементы форм</CardTitle>
                <CardDescription>
                  Компоненты дизайн-системы для построения форм
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-8">
                  {/* GlassInput Examples */}
                  <div className="p-6 border border-white/10 rounded-2xl bg-medium-gray/20">
                    <h4 className="text-lg font-semibold text-white mb-6">GlassInput - поля ввода</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <GlassInput 
                            label="Обычное поле"
                            type="text" 
                            placeholder="Введите текст..."
                          />
                        </div>
                        <div>
                          <GlassInput 
                            label="Поле с иконкой"
                            type="email" 
                            placeholder="example@email.com"
                            icon={<Mail className="w-5 h-5" />}
                          />
                        </div>
                      </div>
                      <div className="space-y-4">
                        <div>
                          <GlassInput 
                            label="Состояние успеха"
                            type="text" 
                            placeholder="Успешная валидация"
                            defaultValue="Корректные данные"
                            success={true}
                          />
                        </div>
                        <div>
                          <GlassInput 
                            label="Состояние ошибки"
                            type="text" 
                            placeholder="Ошибка валидации"
                            defaultValue="Некорректные данные"
                            error="Поле содержит ошибку"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* GlassButton Examples */}
                  <div className="p-6 border border-white/10 rounded-2xl bg-medium-gray/20">
                    <h4 className="text-lg font-semibold text-white mb-6">GlassButton - кнопки</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <h5 className="text-white font-medium">Варианты стилей</h5>
                        <div className="flex flex-wrap gap-4">
                          <GlassButton variant="primary">Primary</GlassButton>
                          <GlassButton variant="secondary">Secondary</GlassButton>
                          <GlassButton variant="outline">Outline</GlassButton>
                          <GlassButton variant="ghost">Ghost</GlassButton>
                          <GlassButton variant="accent">Accent</GlassButton>
                        </div>
                      </div>
                      <div className="space-y-4">
                        <h5 className="text-white font-medium">Размеры</h5>
                        <div className="flex flex-wrap items-center gap-4">
                          <GlassButton variant="primary" size="sm">Small</GlassButton>
                          <GlassButton variant="primary" size="md">Medium</GlassButton>
                          <GlassButton variant="primary" size="lg">Large</GlassButton>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* GlassCard Examples */}
                  <div className="p-6 border border-white/10 rounded-2xl bg-medium-gray/20">
                    <h4 className="text-lg font-semibold text-white mb-6">GlassCard - контейнеры</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <GlassCard variant="default" padding="md">
                        <h5 className="text-white font-medium mb-2">Default Card</h5>
                        <p className="text-text-gray-400 text-sm">Стандартная карточка для группировки элементов</p>
                      </GlassCard>
                      <GlassCard variant="accent" padding="md">
                        <h5 className="text-white font-medium mb-2">Accent Card</h5>
                        <p className="text-text-gray-400 text-sm">Акцентная карточка для важной информации</p>
                      </GlassCard>
                      <GlassCard variant="elevated" padding="md">
                        <h5 className="text-white font-medium mb-2">Elevated Card</h5>
                        <p className="text-text-gray-400 text-sm">Приподнятая карточка с тенью</p>
                      </GlassCard>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Простые формы авторизации */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Простые формы авторизации</CardTitle>
                <CardDescription>
                  Готовые формы входа и регистрации с использованием дизайн-системы
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Форма входа */}
                  <GlassCard variant="default" padding="lg">
                    <div className="space-y-2">
                      <h3 className="text-xl font-semibold text-white">Вход в систему</h3>
                      <p className="text-text-gray-400 text-sm">Авторизуйтесь для доступа к платформе</p>
                    </div>
                    
                    <div className="space-y-4">
                      <GlassInput 
                        label="Email"
                        type="email" 
                        placeholder="example@email.com"
                        icon={<Mail className="w-5 h-5" />}
                      />
                      
                      <GlassInput 
                        label="Пароль"
                        type="password" 
                        placeholder="Введите пароль"
                        icon={<Lock className="w-5 h-5" />}
                        showPasswordToggle={true}
                      />
                    </div>
                    
                    <div className="flex justify-end gap-3 pt-4 border-t border-glass-border">
                      <GlassButton variant="secondary">Отмена</GlassButton>
                      <GlassButton variant="primary">Войти</GlassButton>
                    </div>
                  </GlassCard>

                  {/* Форма регистрации */}
                  <GlassCard variant="default" padding="lg">
                    <div className="space-y-2">
                      <h3 className="text-xl font-semibold text-white">Регистрация</h3>
                      <p className="text-text-gray-400 text-sm">Создайте новый аккаунт в системе</p>
                    </div>
                    
                    <div className="space-y-4">
                      <GlassInput 
                        label="Email"
                        type="email" 
                        placeholder="example@email.com"
                        icon={<Mail className="w-5 h-5" />}
                      />
                      
                      <GlassInput 
                        label="Пароль"
                        type="password" 
                        placeholder="Придумайте пароль"
                        icon={<Lock className="w-5 h-5" />}
                        showPasswordToggle={true}
                      />
                      
                      <GlassInput 
                        label="Подтверждение пароля"
                        type="password" 
                        placeholder="Повторите пароль"
                        icon={<Lock className="w-5 h-5" />}
                        showPasswordToggle={true}
                      />
                    </div>
                    
                    <div className="flex justify-end gap-3 pt-4 border-t border-glass-border">
                      <GlassButton variant="secondary">Отмена</GlassButton>
                      <GlassButton variant="primary">Зарегистрироваться</GlassButton>
                    </div>
                  </GlassCard>
                </div>
              </CardContent>
            </Card>

            {/* Комплексные формы */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Комплексные формы</CardTitle>
                <CardDescription>
                  Многосекционные формы с валидацией и продвинутыми возможностями
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-8">
                  {/* Форма регистрации компании */}
                  <GlassCard variant="default" padding="lg">
                    <div className="space-y-2 mb-6">
                      <h3 className="text-xl font-semibold text-white">Регистрация компании</h3>
                      <p className="text-text-gray-400 text-sm">Заполните данные для создания корпоративного аккаунта</p>
                    </div>
                    
                    <div className="space-y-6">
                      {/* Основная информация */}
                      <FormSection 
                        title="Основная информация"
                        description="Данные о компании и юридической информации"
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <GlassInput 
                            label="Название компании"
                            type="text" 
                            placeholder="ООО «Название»"
                          />
                          <GlassInput 
                            label="ИНН"
                            type="text" 
                            placeholder="1234567890"
                          />
                          <GlassInput 
                            label="КПП"
                            type="text" 
                            placeholder="123456789"
                          />
                          <GlassInput 
                            label="ОГРН"
                            type="text" 
                            placeholder="1234567890123"
                          />
                        </div>
                      </FormSection>

                      {/* Контактные данные */}
                      <FormSection 
                        title="Контактные данные"
                        description="Информация для связи с компанией"
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <GlassInput 
                            label="Email компании"
                            type="email" 
                            placeholder="info@company.com"
                            icon={<Mail className="w-5 h-5" />}
                          />
                          <GlassInput 
                            label="Телефон"
                            type="tel" 
                            placeholder="+7 (xxx) xxx-xx-xx"
                          />
                         <GlassInput 
                           label="Юридический адрес"
                           placeholder="Введите полный юридический адрес"
                         />
                        </div>
                      </FormSection>

                      {/* Представитель компании */}
                      <FormSection 
                        title="Представитель компании"
                        description="Информация о руководителе или уполномоченном лице"
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <GlassInput 
                            label="ФИО директора"
                            type="text" 
                            placeholder="Иванов Иван Иванович"
                            icon={<User className="w-5 h-5" />}
                          />
                          <div className="space-y-2">
                            <Label className="text-white">Должность</Label>
                            <select className="w-full px-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white focus:border-accent-red focus:outline-none transition-colors appearance-none">
                              <option value="">Выберите должность</option>
                              <option value="director">Генеральный директор</option>
                              <option value="manager">Менеджер</option>
                              <option value="logist">Логист</option>
                            </select>
                          </div>
                        </div>
                      </FormSection>

                      {/* Настройки и соглашения */}
                      <FormSection 
                        title="Настройки и соглашения"
                        description="Принятие условий использования и настройки уведомлений"
                        actions={
                          <>
                            <GlassButton variant="secondary">Отмена</GlassButton>
                            <GlassButton variant="primary">Зарегистрировать компанию</GlassButton>
                          </>
                        }
                      >
                        <div className="space-y-4">
                          <div className="flex items-center space-x-3">
                            <Checkbox id="terms-agreement" />
                            <Label htmlFor="terms-agreement" className="text-white text-sm">Согласен с условиями использования</Label>
                          </div>
                          <div className="flex items-center space-x-3">
                            <Checkbox id="privacy-policy" />
                            <Label htmlFor="privacy-policy" className="text-white text-sm">Согласен на обработку персональных данных</Label>
                          </div>
                          <div className="flex items-center space-x-3">
                            <Checkbox id="newsletter" />
                            <Label htmlFor="newsletter" className="text-white text-sm">Получать новости и обновления</Label>
                          </div>
                        </div>
                      </FormSection>
                    </div>
                  </GlassCard>
                </div>
              </CardContent>
            </Card>

            {/* Специализированные формы */}
            <Card>
              <CardHeader>
                <CardTitle className="text-accent-red">Специализированные формы</CardTitle>
                <CardDescription>
                  Формы для специфических задач: поиск, фильтрация, профили
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-8">
                  {/* Форма поиска и фильтрации */}
                  <div className="p-6 rounded-xl bg-medium-gray/60 border border-white/10 backdrop-blur-sm space-y-6">
                    <div className="space-y-2">
                      <h3 className="text-xl font-semibold text-white">Расширенный поиск</h3>
                      <p className="text-text-gray-400 text-sm">Найдите нужную информацию с помощью фильтров</p>
                    </div>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-white mb-2">Поиск</label>
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                          <input 
                            type="text" 
                            placeholder="Введите запрос для поиска..."
                            className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white placeholder:text-text-gray-400 focus:border-accent-red focus:outline-none transition-colors"
                          />
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-white mb-2">Категория</label>
                          <div className="relative">
                            <select className="w-full px-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white focus:border-accent-red focus:outline-none transition-colors appearance-none">
                              <option value="">Все категории</option>
                              <option value="logistics">Логистика</option>
                              <option value="transport">Транспорт</option>
                              <option value="warehouse">Склад</option>
                            </select>
                            <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400 pointer-events-none" />
                          </div>
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-white mb-2">Дата от</label>
                          <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                            <input 
                              type="date" 
                              className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white focus:border-accent-red focus:outline-none transition-colors"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-white mb-2">Дата до</label>
                          <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                            <input 
                              type="date" 
                              className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white focus:border-accent-red focus:outline-none transition-colors"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
                      <Button variant="outline">Сбросить фильтры</Button>
                      <Button variant="accent">Применить фильтры</Button>
                    </div>
                  </div>

                  {/* Форма профиля пользователя */}
                  <div className="p-6 rounded-xl bg-medium-gray/60 border border-white/10 backdrop-blur-sm space-y-6">
                    <div className="space-y-2">
                      <h3 className="text-xl font-semibold text-white">Редактирование профиля</h3>
                      <p className="text-text-gray-400 text-sm">Обновите информацию в вашем профиле</p>
                    </div>
                    
                    <div className="space-y-4">
                      {/* Личная информация */}
                      <div className="p-4 rounded-xl bg-[#1a1a1d] border border-white/5">
                        <h5 className="text-white font-medium mb-4">Личная информация</h5>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-white mb-2">Имя</label>
                            <div className="relative">
                              <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                              <input 
                                type="text" 
                                placeholder="Введите имя"
                                className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white placeholder:text-text-gray-400 focus:border-accent-red focus:outline-none transition-colors"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-white mb-2">Фамилия</label>
                            <div className="relative">
                              <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                              <input 
                                type="text" 
                                placeholder="Введите фамилию"
                                className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white placeholder:text-text-gray-400 focus:border-accent-red focus:outline-none transition-colors"
                              />
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Контактная информация */}
                      <div className="p-4 rounded-xl bg-[#1a1a1d] border border-white/5">
                        <h5 className="text-white font-medium mb-4">Контактная информация</h5>
                        <div className="space-y-4">
                          <div>
                            <label className="block text-sm font-medium text-white mb-2">Email</label>
                            <div className="relative">
                              <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-gray-400" />
                              <input 
                                type="email" 
                                placeholder="example@email.com"
                                className="w-full pl-10 pr-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white placeholder:text-text-gray-400 focus:border-accent-red focus:outline-none transition-colors"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-white mb-2">Телефон</label>
                            <input 
                              type="tel" 
                              placeholder="+7 (xxx) xxx-xx-xx"
                              className="w-full px-4 py-3 rounded-xl bg-[#1a1a1d] border border-white/10 text-white placeholder:text-text-gray-400 focus:border-accent-red focus:outline-none transition-colors"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Настройки уведомлений */}
                      <div className="p-4 rounded-xl bg-[#1a1a1d] border border-white/5">
                        <h5 className="text-white font-medium mb-4">Настройки уведомлений</h5>
                        <div className="space-y-4">
                          <div className="flex items-center space-x-3">
                            <input 
                              type="checkbox" 
                              id="email-notifications-profile"
                              className="w-4 h-4 rounded border border-white/20 bg-[#1a1a1d] checked:bg-accent-red checked:border-accent-red focus:ring-accent-red focus:ring-2 focus:ring-offset-0"
                            />
                            <label htmlFor="email-notifications-profile" className="text-white text-sm">Получать email уведомления</label>
                          </div>
                          <div className="flex items-center space-x-3">
                            <input 
                              type="checkbox" 
                              id="push-notifications-profile"
                              className="w-4 h-4 rounded border border-white/20 bg-[#1a1a1d] checked:bg-accent-red checked:border-accent-red focus:ring-accent-red focus:ring-2 focus:ring-offset-0"
                            />
                            <label htmlFor="push-notifications-profile" className="text-white text-sm">Push уведомления</label>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
                      <Button variant="outline">Отмена</Button>
                      <Button variant="accent">Сохранить изменения</Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <footer className="text-center mt-16 pt-8 border-t border-white/10">
          <p className="text-gray-400">
            © 2025 WellWon Design System. Создано с ❤️ для современных веб-приложений
          </p>
        </footer>
      </div>
    </div>;
};
export default DesignPage;