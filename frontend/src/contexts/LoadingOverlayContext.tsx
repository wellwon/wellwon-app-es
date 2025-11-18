import React, { createContext, useContext, useState, ReactNode } from 'react';

interface LoadingOverlayState {
  isVisible: boolean;
  message: string;
  progress: number;
  steps: string[];
  currentStep: number;
  stepStatuses: ('pending' | 'loading' | 'success' | 'error')[];
  errorMessage?: string;
  resultData?: {
    companyName?: string;
    telegramGroup?: {
      title: string;
      link: string;
      qrCodeUrl?: string;
    };
  };
}

interface LoadingOverlayContextType {
  state: LoadingOverlayState;
  showLoading: (message: string, steps: string[]) => void;
  updateStep: (stepIndex: number, status: 'loading' | 'success' | 'error', progress?: number) => void;
  setError: (errorMessage: string) => void;
  setResult: (resultData: LoadingOverlayState['resultData']) => void;
  hideLoading: () => void;
}

const LoadingOverlayContext = createContext<LoadingOverlayContextType | undefined>(undefined);

export const useLoadingOverlay = () => {
  const context = useContext(LoadingOverlayContext);
  if (!context) {
    throw new Error('useLoadingOverlay must be used within LoadingOverlayProvider');
  }
  return context;
};

interface LoadingOverlayProviderProps {
  children: ReactNode;
}

export const LoadingOverlayProvider: React.FC<LoadingOverlayProviderProps> = ({ children }) => {
  const [state, setState] = useState<LoadingOverlayState>({
    isVisible: false,
    message: '',
    progress: 0,
    steps: [],
    currentStep: 0,
    stepStatuses: [],
    errorMessage: undefined,
    resultData: undefined
  });

  const showLoading = (message: string, steps: string[]) => {
    setState({
      isVisible: true,
      message,
      progress: 0,
      steps,
      currentStep: 0,
      stepStatuses: steps.map(() => 'pending' as const),
      errorMessage: undefined,
      resultData: undefined
    });
  };

  const updateStep = (stepIndex: number, status: 'loading' | 'success' | 'error', progress?: number) => {
    setState(prev => {
      const newStepStatuses = [...prev.stepStatuses];
      
      // Обновляем статус указанного этапа
      newStepStatuses[stepIndex] = status;
      
      // Если это успешный этап, обновляем текущий этап
      const newCurrentStep = status === 'success' ? Math.min(stepIndex + 1, prev.steps.length - 1) : stepIndex;
      
      return {
        ...prev,
        currentStep: newCurrentStep,
        stepStatuses: newStepStatuses,
        progress: progress ?? prev.progress
      };
    });
  };

  const setError = (errorMessage: string) => {
    setState(prev => {
      const newStepStatuses = [...prev.stepStatuses];
      
      // Помечаем текущий этап как error
      if (prev.currentStep < newStepStatuses.length) {
        newStepStatuses[prev.currentStep] = 'error';
      }
      
      return {
        ...prev,
        stepStatuses: newStepStatuses,
        errorMessage
      };
    });
  };

  const setResult = (resultData: LoadingOverlayState['resultData']) => {
    setState(prev => ({
      ...prev,
      progress: 100,
      stepStatuses: prev.stepStatuses.map(() => 'success' as const),
      resultData
    }));
  };

  const hideLoading = () => {
    setState(prev => ({
      ...prev,
      isVisible: false,
      errorMessage: undefined,
      resultData: undefined
    }));
  };

  return (
    <LoadingOverlayContext.Provider value={{ state, showLoading, updateStep, setError, setResult, hideLoading }}>
      {children}
    </LoadingOverlayContext.Provider>
  );
};