import React, { useState, useRef, useEffect } from 'react';


interface OptimizedImageProps {
  src: string;
  alt: string;
  className?: string;
  onClick?: () => void;
  onError?: () => void;
  // Предустановленные размеры для предотвращения layout shift
  initialWidth?: number;
  initialHeight?: number;
  aspectRatio?: number;
  fit?: 'cover' | 'contain';
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  alt,
  className = '',
  onClick,
  onError,
  initialWidth,
  initialHeight,
  aspectRatio,
  fit = 'cover'
}) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Reset states when src changes
  useEffect(() => {
    setIsLoaded(false);
    setHasError(false);
  }, [src]);

  const handleLoad = () => {
    setIsLoaded(true);
  };

  const handleError = () => {
    setHasError(true);
    onError?.();
  };

  if (hasError) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded ${className}`}>
        <span className="text-muted-foreground text-sm">Изображение недоступно</span>
      </div>
    );
  }

  // Вычисляем стили контейнера для предотвращения layout shift
  const containerStyle: React.CSSProperties = {};
  
  if (aspectRatio) {
    containerStyle.aspectRatio = aspectRatio.toString();
  } else if (initialWidth && initialHeight) {
    containerStyle.aspectRatio = (initialWidth / initialHeight).toString();
  }

  return (
    <div 
      ref={imgRef} 
      className={`relative bg-muted/20 ${className}`}
      style={containerStyle}
    >
      <img
        src={src}
        alt={alt}
        className={`w-full h-full object-${fit} transition-opacity duration-200 ${
          isLoaded ? 'opacity-100' : 'opacity-0'
        }`}
        onLoad={handleLoad}
        onError={handleError}
        onClick={onClick}
        loading="lazy"
      />
    </div>
  );
};