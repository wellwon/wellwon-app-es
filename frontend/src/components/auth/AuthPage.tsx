import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { GlassInput } from '@/components/design-system/GlassInput';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { Eye, EyeOff, ArrowLeft, MessageCircle, Bot, CheckCircle } from 'lucide-react';
type AuthMode = 'login' | 'signup' | 'forgot' | 'magic';
type RegistrationStep = 'form' | 'completing' | 'success';

const AuthPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const {
    signIn,
    signUp,
    signInWithMagicLink,
    user,
    loading
  } = useAuth();
  const {
    toast
  } = useToast();
  const [mode, setMode] = useState<AuthMode>(() => {
    return searchParams.get('mode') as AuthMode || 'login';
  });
  const [registrationStep, setRegistrationStep] = useState<RegistrationStep>('form');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Анимация чата
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [typingText, setTypingText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatMessages = [{
    type: 'user',
    text: 'Нужно найти поставщика для офисной мебели'
  }, {
    type: 'bot',
    text: 'Анализирую ваши потребности...'
  }, {
    type: 'bot',
    text: 'Нашел 15 проверенных поставщиков офисной мебели'
  }, {
    type: 'bot',
    text: 'Лучшее предложение: скидка 25%, доставка бесплатно'
  }, {
    type: 'system',
    text: 'Сделка успешно завершена! Экономия: 180,000₽'
  }];

  // Перенаправляем авторизованных пользователей (только не во время регистрации)
  useEffect(() => {
    console.log('[AuthPage] useEffect: user=', user, 'loading=', loading, 'registrationStep=', registrationStep);
    if (user && !loading && registrationStep !== 'success' && registrationStep !== 'completing') {
      // Проверяем redirect параметр (игнорируем корневой путь и пути к /platform)
      const redirectParam = searchParams.get('redirect');
      const isValidRedirect = redirectParam && redirectParam !== '/' && !redirectParam.startsWith('/platform');
      const redirectTo = isValidRedirect ? redirectParam : '/platform-pro/declarant';
      console.log('[AuthPage] useEffect: conditions met, navigating to', redirectTo);
      navigate(redirectTo);
    }
  }, [user, loading, navigate, registrationStep, searchParams]);

  // Анимация печатания в чате
  useEffect(() => {
    if (currentMessageIndex >= chatMessages.length) {
      setTimeout(() => {
        setCurrentMessageIndex(0);
        setTypingText('');
      }, 3000);
      return;
    }
    const currentMessage = chatMessages[currentMessageIndex];
    setIsTyping(true);
    let charIndex = 0;
    setTypingText('');
    const typingInterval = setInterval(() => {
      if (charIndex < currentMessage.text.length) {
        setTypingText(prev => prev + currentMessage.text[charIndex]);
        charIndex++;
      } else {
        clearInterval(typingInterval);
        setIsTyping(false);
        setTimeout(() => {
          setCurrentMessageIndex(prev => prev + 1);
        }, 1500);
      }
    }, 50);
    return () => clearInterval(typingInterval);
  }, [currentMessageIndex]);
  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };
  const validateForm = () => {
    if (!formData.email) {
      toast({
        title: 'Ошибка',
        description: 'Введите email',
        variant: 'error'
      });
      return false;
    }
    if (mode === 'signup' || mode === 'login') {
      if (!formData.password) {
        toast({
          title: 'Ошибка',
          description: 'Введите пароль',
          variant: 'error'
        });
        return false;
      }
      if (mode === 'signup') {
        if (!formData.firstName || !formData.firstName.trim()) {
          toast({
            title: 'Ошибка',
            description: 'Введите имя',
            variant: 'error'
          });
          return false;
        }
        if (!formData.lastName || !formData.lastName.trim()) {
          toast({
            title: 'Ошибка',
            description: 'Введите фамилию',
            variant: 'error'
          });
          return false;
        }
        if (formData.password !== formData.confirmPassword) {
          toast({
            title: 'Ошибка',
            description: 'Пароли не совпадают',
            variant: 'error'
          });
          return false;
        }
        if (formData.password.length < 6) {
          toast({
            title: 'Ошибка',
            description: 'Пароль должен содержать минимум 6 символов',
            variant: 'error'
          });
          return false;
        }
      }
    }
    return true;
  };
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    
    // For signup, proceed directly to registration
    if (mode === 'signup') {
      await handleRegistration();
      return;
    }
    
    setIsSubmitting(true);
    try {
      let result;
      switch (mode) {
        case 'login':
          result = await signIn(formData.email, formData.password);
          break;
        case 'magic':
          result = await signInWithMagicLink(formData.email);
          break;
        default:
          return;
      }
      if (result.error) {
        toast({
          title: 'Ошибка авторизации',
          description: result.error.message,
          variant: 'error'
        });
      } else {
        if (mode === 'magic') {
          toast({
            title: 'Magic link отправлен!',
            description: 'Проверьте email для входа',
            variant: 'success'
          });
        } else {
          toast({
            title: 'Добро пожаловать!',
            description: 'Вы успешно вошли в систему',
            variant: 'success'
          });
          // Navigation is handled by useEffect watching user state
        }
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Произошла неожиданная ошибка',
        variant: 'error'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegistration = async () => {
    setIsSubmitting(true);
    
    try {
      const result = await signUp(formData.email, formData.password, {
        first_name: formData.firstName,
        last_name: formData.lastName,
        user_type: 'ww_manager' // Default to manager type
      });
      
      if (result.error) {
        // Handle rate limiting specifically
        if (result.error.message?.includes('rate_limit') || result.error.message?.includes('rate limit')) {
          toast({
            title: 'Слишком много попыток',
            description: 'Пожалуйста, подождите 60 секунд перед следующей попыткой',
            variant: 'error'
          });
        } else {
          toast({
            title: 'Ошибка регистрации',
            description: result.error.message,
            variant: 'error'
          });
        }
        // Keep user type selection open on error
      } else {
        // Show success message and proceed to success screen
        toast({
          title: 'Регистрация успешна!',
          description: 'Добро пожаловать в WellWon!',
          variant: 'success'
        });
        // Immediately show success page without delay
        setRegistrationStep('success');
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Произошла неожиданная ошибка',
        variant: 'error'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackToForm = () => {
    setRegistrationStep('form');
  };
  const renderForm = () => {
    switch (mode) {
      case 'login':
        return <>
            <GlassInput label="Email" type="email" value={formData.email} onChange={e => handleInputChange('email', e.target.value)} placeholder="your@email.com" />
            
            <GlassInput label="Пароль" type={showPassword ? 'text' : 'password'} value={formData.password} onChange={e => handleInputChange('password', e.target.value)} showPasswordToggle placeholder="Введите пароль" />
          </>;
      case 'signup':
        return <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <GlassInput label="Имя" type="text" value={formData.firstName} onChange={e => handleInputChange('firstName', e.target.value)} placeholder="Ваше имя" />
              
              <GlassInput label="Фамилия" type="text" value={formData.lastName} onChange={e => handleInputChange('lastName', e.target.value)} placeholder="Ваша фамилия" />
            </div>
            
            <GlassInput label="Email" type="email" value={formData.email} onChange={e => handleInputChange('email', e.target.value)} placeholder="your@email.com" />
            
            <GlassInput label="Пароль" type={showPassword ? 'text' : 'password'} value={formData.password} onChange={e => handleInputChange('password', e.target.value)} showPasswordToggle placeholder="Минимум 6 символов" />
            
            <GlassInput label="Подтвердите пароль" type={showPassword ? 'text' : 'password'} value={formData.confirmPassword} onChange={e => handleInputChange('confirmPassword', e.target.value)} showPasswordToggle placeholder="Повторите пароль" />
          </>;
      case 'magic':
        return <GlassInput label="Email" type="email" value={formData.email} onChange={e => handleInputChange('email', e.target.value)} placeholder="your@email.com" />;
      default:
        return null;
    }
  };
  const getModeTitle = () => {
    switch (mode) {
      case 'login':
        return 'Вход в систему';
      case 'signup':
        return 'Создать аккаунт';
      case 'magic':
        return 'Magic Link';
      default:
        return 'Авторизация';
    }
  };
  const getSubmitButtonText = () => {
    switch (mode) {
      case 'login':
        return 'Войти';
      case 'signup':
        return 'Продолжить';
      case 'magic':
        return 'Отправить Magic Link';
      default:
        return 'Отправить';
    }
  };
  if (loading) {
    return <div className="min-h-screen bg-gradient-dark flex items-center justify-center">
        <div className="text-white">Загрузка...</div>
      </div>;
  }


  // Show success message after registration
  if (mode === 'signup' && registrationStep === 'success') {
    return (
      <div className="min-h-screen bg-dark-gray flex flex-col justify-center px-8 lg:px-16 relative">
        <div className="max-w-2xl mx-auto w-full text-center">
          <div className="mb-8">
            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-green-500" />
            </div>
            <h1 className="text-4xl font-bold text-white mb-4">
              Регистрация успешна!
            </h1>
            <p className="text-gray-400 text-lg">
              Добро пожаловать в WellWon! Нажмите кнопку ниже, чтобы перейти к платформе.
            </p>
          </div>
          
          <div className="flex justify-center">
            <GlassButton
              variant="secondary"
              size="lg"
              onClick={() => navigate('/platform-pro/declarant')}
              className="min-w-[200px]"
            >
              Перейти к платформе
            </GlassButton>
          </div>
        </div>
      </div>
    );
  }
  return <div className="min-h-screen flex">
      {/* Левая панель - Форма авторизации */}
      <div className="w-full lg:w-1/2 bg-dark-gray flex flex-col justify-center px-8 lg:px-16 relative">
        {/* Кнопка назад */}
        <button onClick={() => navigate('/')} className="absolute top-8 left-8 flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          На главную
        </button>

        <div className="max-w-sm mx-auto w-full">
          {/* Логотип */}
          <div className="mb-8">
            <div className="flex justify-start mb-4">
              <div className="w-16 h-16 rounded-2xl bg-accent-red overflow-hidden">
                <img 
                  src="/lovable-uploads/ecc7d3c5-0cff-4d25-9f28-5f02170ca37a.png" 
                  alt="WellWon Logo" 
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">
              {getModeTitle()}
            </h1>
            
          </div>


          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {renderForm()}

            {/* Согласие с политикой при регистрации */}
            {mode === 'signup' && <div className="flex items-center gap-3">
                <input 
                  type="checkbox" 
                  id="terms-consent" 
                  required 
                  defaultChecked 
                  className="w-5 h-5 rounded-full appearance-none border-2 border-gray-500 bg-transparent checked:bg-white checked:border-white relative cursor-pointer transition-all duration-200 focus:outline-none focus:ring-0" 
                  style={{
                    backgroundImage: 'url("data:image/svg+xml,%3csvg viewBox=\'0 0 16 16\' fill=\'%23000\' xmlns=\'http://www.w3.org/2000/svg\'%3e%3cpath d=\'M12.207 4.793a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0l-2-2a1 1 0 011.414-1.414L6.5 9.086l4.293-4.293a1 1 0 011.414 0z\'/%3e%3c/svg%3e")',
                    backgroundSize: '12px 12px',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat'
                  }}
                />
                <label htmlFor="terms-consent" className="text-[11px] text-gray-300 leading-tight">
                  Я согласен с{' '}
                  <a href="/terms" target="_blank" className="text-white underline hover:text-accent-red transition-colors">
                    Условиями
                  </a>
                  {' '}и{' '}
                  <a href="/privacy" target="_blank" className="text-white underline hover:text-accent-red transition-colors">
                    Политикой конфиденциальности
                  </a>
                </label>
              </div>}

            <GlassButton type="submit" variant="primary" size="md" loading={isSubmitting} className="w-full">
              {getSubmitButtonText()}
            </GlassButton>
          </form>

          {/* Переключение между режимами */}
          <div className="mt-6 space-y-4 text-center">
            {mode === 'login' && <>
                <button type="button" onClick={() => setMode('magic')} className="text-white hover:text-accent-red text-sm transition-colors underline">
                  Забыли пароль?
                </button>
                
                <p className="text-gray-400 text-sm">
                  Нет аккаунта?{' '}
                <button type="button" onClick={() => {
                  setMode('signup');
                  setRegistrationStep('form');
                }} className="text-white hover:text-accent-red transition-colors underline">Регистрация</button>
                </p>
              </>}

            {mode === 'signup' && <p className="text-gray-400 text-sm">
                Уже есть аккаунт?{' '}
                <button type="button" onClick={() => {
                  setMode('login');
                  setRegistrationStep('form');
                }} className="text-white underline hover:text-accent-red transition-colors">
                  Войти
                </button>
              </p>}

            {mode === 'magic' && <button type="button" onClick={() => setMode('login')} className="text-accent-red hover:text-accent-red/80 text-sm transition-colors">
                Назад к входу
              </button>}
          </div>
        </div>
      </div>

      {/* Правая панель - Анимированный чат и логотип */}
      <div 
        className="hidden lg:flex lg:w-1/2 relative overflow-hidden" 
        style={{
          backgroundImage: `url('/lovable-uploads/8a830bf6-14d1-443d-a7df-93c547caf654.png')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
      >
        
        <div className="relative z-10 flex flex-col justify-between p-16 text-white w-full">
          {/* Логотип и заголовок */}
          <div>
            <div className="flex flex-col leading-tight mb-4">
              <div className="text-accent-red text-4xl font-black tracking-tight relative">
                Well<span className="text-white">Won</span>
                <div className="absolute -bottom-1 left-0 w-12 h-0.5 bg-accent-red"></div>
              </div>
            </div>
            <p className="text-xl text-white/80 mb-8">
              Платформа умных закупок
            </p>
          </div>

          {/* Анимированный чат */}
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-md">
              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 space-y-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                    <MessageCircle className="w-4 h-4" />
                  </div>
                  <span className="font-medium">Чат с AI помощником</span>
                </div>

                {/* Сообщения чата */}
                <div className="space-y-3 h-64 overflow-hidden">
                  {chatMessages.slice(0, currentMessageIndex).map((message, index) => <div key={index} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                      <div className={`max-w-[80%] p-3 rounded-xl ${message.type === 'user' ? 'bg-white text-gray-900' : message.type === 'system' ? 'bg-green-500/20 border border-green-400/30 text-green-100' : 'bg-white/20 text-white'}`}>
                        {message.type === 'bot' && <div className="flex items-center gap-2 mb-1">
                            <Bot className="w-3 h-3" />
                            <span className="text-xs opacity-70">AI помощник</span>
                          </div>}
                        {message.type === 'system' && <div className="flex items-center gap-2 mb-1">
                            <CheckCircle className="w-3 h-3" />
                            <span className="text-xs opacity-70">Система</span>
                          </div>}
                        <p className="text-sm">{message.text}</p>
                      </div>
                    </div>)}
                  
                  {/* Текущее печатающееся сообщение */}
                  {currentMessageIndex < chatMessages.length && <div className={`flex ${chatMessages[currentMessageIndex].type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] p-3 rounded-xl ${chatMessages[currentMessageIndex].type === 'user' ? 'bg-white text-gray-900' : chatMessages[currentMessageIndex].type === 'system' ? 'bg-green-500/20 border border-green-400/30 text-green-100' : 'bg-white/20 text-white'}`}>
                        {chatMessages[currentMessageIndex].type === 'bot' && <div className="flex items-center gap-2 mb-1">
                            <Bot className="w-3 h-3" />
                            <span className="text-xs opacity-70">AI помощник</span>
                          </div>}
                        {chatMessages[currentMessageIndex].type === 'system' && <div className="flex items-center gap-2 mb-1">
                            <CheckCircle className="w-3 h-3" />
                            <span className="text-xs opacity-70">Система</span>
                          </div>}
                        <p className="text-sm">
                          {typingText}
                          {isTyping && <span className="animate-pulse">|</span>}
                        </p>
                      </div>
                    </div>}
                </div>

                {/* Индикатор печатания */}
                {isTyping && <div className="flex items-center gap-2 text-white/60">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse"></div>
                      <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse" style={{
                    animationDelay: '0.2s'
                  }}></div>
                      <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse" style={{
                    animationDelay: '0.4s'
                  }}></div>
                    </div>
                    <span className="text-xs">Печатает...</span>
                  </div>}
              </div>
            </div>
          </div>

          {/* Нижний текст */}
          <div className="text-center">
            <p className="text-white/80">
              Присоединяйтесь к тысячам компаний, которые уже экономят с WellWon
            </p>
          </div>
        </div>
      </div>
    </div>;
};
export default AuthPage;