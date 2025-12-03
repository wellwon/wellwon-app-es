import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Mic, Square, Loader2, Play, Pause, Send, Trash2 } from 'lucide-react';
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
  // Preview state
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewDuration, setPreviewDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const { sendVoice } = useRealtimeChatContext();
  const { toast } = useToast();
  const { isLightTheme } = usePlatform();

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Create MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      // Event handlers
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Create blob for preview (don't auto-send)
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setPreviewBlob(audioBlob);
        setPreviewDuration(recordingTime);
      };

      // Start recording
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          const newTime = prev + 1;
          // Auto-stop after 5 minutes
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

  const handlePreviewPlay = () => {
    if (!previewBlob) return;

    if (!audioRef.current) {
      audioRef.current = new Audio(URL.createObjectURL(previewBlob));
      audioRef.current.onended = () => setIsPlaying(false);
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleSend = async () => {
    if (!previewBlob) return;

    setIsProcessing(true);

    try {
      await sendVoice(previewBlob, previewDuration);

      toast({
        title: "Голосовое сообщение отправлено",
        description: `Длительность: ${previewDuration}с`,
      });

      // Cleanup
      handleDiscard();
    } catch (error) {
      toast({
        title: "Ошибка отправки",
        description: "Не удалось отправить голосовое сообщение",
        variant: "error"
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDiscard = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPreviewBlob(null);
    setPreviewDuration(0);
    setIsPlaying(false);
    setRecordingTime(0);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Processing state
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

  // Preview mode - show play/send/discard controls
  if (previewBlob) {
    return (
      <div className="flex items-center gap-1">
        {/* Duration */}
        <span className={`text-xs font-mono ${isLightTheme ? 'text-gray-600' : 'text-gray-400'}`}>
          {formatTime(previewDuration)}
        </span>

        {/* Play/Pause button */}
        <Button
          variant="ghost"
          size="icon"
          className={`rounded-full h-9 w-9 ${
            isLightTheme
              ? 'text-gray-600 hover:text-accent-red hover:bg-accent-red/10'
              : 'text-gray-400 hover:text-accent-red hover:bg-accent-red/10'
          }`}
          onClick={handlePreviewPlay}
        >
          {isPlaying ? <Pause size={18} /> : <Play size={18} />}
        </Button>

        {/* Discard button */}
        <Button
          variant="ghost"
          size="icon"
          className={`rounded-full h-9 w-9 ${
            isLightTheme
              ? 'text-gray-500 hover:text-red-500 hover:bg-red-500/10'
              : 'text-gray-400 hover:text-red-400 hover:bg-red-400/10'
          }`}
          onClick={handleDiscard}
        >
          <Trash2 size={18} />
        </Button>

        {/* Send button */}
        <Button
          variant="ghost"
          size="icon"
          className="text-accent-red bg-accent-red/20 hover:bg-accent-red/30 rounded-full h-11 w-11"
          onClick={handleSend}
        >
          <Send size={20} />
        </Button>
      </div>
    );
  }

  // Recording state
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

  // Default state - mic button
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
