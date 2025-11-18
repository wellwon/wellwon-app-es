
import React, { useState, useRef } from 'react';
import { Play, Pause, Maximize2 } from 'lucide-react';


interface VideoPlayerProps {
  src: string;
  poster?: string;
  className?: string;
}

const VideoPlayer = ({ src, poster, className = "" }: VideoPlayerProps) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (videoRef.current.requestFullscreen) {
        videoRef.current.requestFullscreen();
      }
    }
  };

  const handleLoadedData = () => {
    setIsLoading(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
  };

  if (hasError) {
    return (
      <div className={`relative group rounded-3xl overflow-hidden bg-gray-800 aspect-video flex items-center justify-center ${className}`}>
        <div className="text-white text-center">
          <p className="text-lg mb-2">Ошибка загрузки видео</p>
          <p className="text-sm text-gray-400">Попробуйте обновить страницу</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`relative group rounded-3xl overflow-hidden ${className}`}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      {/* Индикатор загрузки */}
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-gray-800/50">
          <div className="w-20 h-20 border-4 border-accent-red border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}

      <video
        ref={videoRef}
        src={src}
        poster={poster}
        className="w-full h-full object-cover"
        autoPlay
        muted
        loop
        playsInline
        onLoadedData={handleLoadedData}
        onError={handleError}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />
      
      {/* Градиентная рамка */}
      <div className="absolute inset-0 rounded-3xl border-2 border-gradient-to-r from-accent-red/50 via-accent-red to-accent-red/50 pointer-events-none" />
      
      {/* Контролы */}
      {showControls && !isLoading && (
        <div className="absolute inset-0 bg-black/20 transition-opacity duration-300 opacity-0 group-hover:opacity-100">
          <div className="absolute inset-0 flex items-center justify-center">
            <button
              onClick={togglePlay}
              className="w-20 h-20 bg-white/90 hover:bg-white rounded-full flex items-center justify-center text-dark-gray hover:scale-110 transition-all duration-300 shadow-lg"
            >
              {isPlaying ? (
                <Pause className="w-8 h-8 ml-1" />
              ) : (
                <Play className="w-8 h-8 ml-1" />
              )}
            </button>
          </div>
          
          <div className="absolute bottom-4 right-4">
            <button
              onClick={toggleFullscreen}
              className="w-10 h-10 bg-white/80 hover:bg-white rounded-full flex items-center justify-center text-dark-gray hover:scale-110 transition-all duration-300"
            >
              <Maximize2 className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
      
      {/* Декоративные элементы */}
      <div className="absolute -top-2 -left-2 w-4 h-4 bg-accent-red rounded-full animate-pulse" />
      <div className="absolute -bottom-2 -right-2 w-3 h-3 bg-accent-red rounded-full animate-pulse" style={{ animationDelay: '1s' }} />
    </div>
  );
};

export default VideoPlayer;
