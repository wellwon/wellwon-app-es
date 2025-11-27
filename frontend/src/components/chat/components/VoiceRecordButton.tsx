import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Mic, Square, Loader2 } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useToast } from '@/hooks/use-toast';
import { usePlatform } from '@/contexts/PlatformContext';

interface VoiceRecordButtonProps {
  disabled?: boolean;
}

export function VoiceRecordButton({ disabled }: VoiceRecordButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const { sendVoice } = useRealtimeChatContext();
  const { toast } = useToast();
  const { isLightTheme } = usePlatform();

  // Очистка ресурсов при размонтировании
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      // Запрашиваем разрешение на микрофон
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      // Создаем MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      // Обработчики событий
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        
        try {
          const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
          await sendVoice(audioBlob, recordingTime);
          
          toast({
            title: "Голосовое сообщение отправлено",
            description: `Длительность: ${recordingTime}с`,
          });
        } catch (error) {
          
          toast({
            title: "Ошибка отправки",
            description: "Не удалось отправить голосовое сообщение",
            variant: "error"
          });
        } finally {
          setIsProcessing(false);
          setRecordingTime(0);
        }
      };

      // Начинаем запись
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      
      // Запускаем таймер
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          const newTime = prev + 1;
          // Автоматически останавливаем запись через 5 минут
          if (newTime >= 300) {
            stopRecording();
          }
          return newTime;
        });
      }, 1000);
      
      toast({
        title: "Запись началась",
        description: "Говорите в микрофон",
      });
    } catch (error) {
      
      toast({
        title: "Ошибка доступа к микрофону",
        description: "Разрешите доступ к микрофону для записи голосовых сообщений",
        variant: "error"
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (isProcessing) {
    return (
      <Button 
        variant="ghost" 
        size="icon" 
        className="text-accent-red rounded-full h-11 w-11"
        disabled
      >
        <Loader2 size={22} className="animate-spin" />
      </Button>
    );
  }

  if (isRecording) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-accent-red font-mono">
          {formatTime(recordingTime)}
        </span>
        <Button 
          variant="ghost" 
          size="icon" 
          className="text-accent-red bg-accent-red/20 rounded-full h-11 w-11 animate-pulse"
          onClick={stopRecording}
        >
          <Square size={22} />
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className={`rounded-full h-11 w-11 transition-all ${
        isLightTheme
          ? 'text-gray-500 hover:text-accent-red bg-[#e8e8e8] hover:bg-accent-red/10 border border-gray-300 hover:border-accent-red/30'
          : 'text-gray-400 hover:text-accent-red hover:bg-accent-red/10 border border-transparent hover:border-accent-red/30'
      }`}
      onClick={startRecording}
      disabled={disabled}
    >
      <Mic size={22} />
    </Button>
  );
}