import React from 'react';

const PageLoader = () => {
  return (
    <div className="fixed inset-0 bg-dark-gray flex items-center justify-center z-50">
      <div className="flex flex-col items-center space-y-4">
        {/* Анимированные точки */}
        <div className="flex space-x-2">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="w-3 h-3 bg-accent-red rounded-full animate-pulse"
              style={{
                animationDelay: `${index * 0.2}s`,
                animationDuration: '1s'
              }}
            />
          ))}
        </div>
        
        {/* Текст загрузки */}
        <p className="text-text-gray-400 text-sm">Загрузка...</p>
      </div>
    </div>
  );
};

export default PageLoader;