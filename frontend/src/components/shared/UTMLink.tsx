
import React from 'react';
import { Link, LinkProps } from 'react-router-dom';
import { useUTMContext } from '@/contexts/UTMContext';

interface UTMLinkProps extends Omit<LinkProps, 'to'> {
  to: string;
  external?: boolean;
}

const UTMLink: React.FC<UTMLinkProps> = ({ 
  to, 
  external = false, 
  children, 
  ...props 
}) => {
  const { appendUTMToURL, utmParams } = useUTMContext();

  if (external) {
    // Для внешних ссылок используем обычный a тег
    const urlWithUTM = appendUTMToURL(to);
    return (
      <a 
        href={urlWithUTM} 
        target="_blank" 
        rel="noopener noreferrer"
        {...(props as any)}
      >
        {children}
      </a>
    );
  }

  // Для внутренних ссылок добавляем UTM параметры как query params
  const getInternalLinkWithUTM = (path: string): string => {
    if (Object.keys(utmParams).length === 0) return path;

    // Проверяем, есть ли уже параметры в URL
    const [pathname, search, hash] = path.split(/[?#]/);
    const urlParams = new URLSearchParams(search || '');
    
    // Добавляем UTM параметры, если их еще нет
    Object.entries(utmParams).forEach(([key, value]) => {
      if (value && !urlParams.has(key)) {
        urlParams.set(key, value);
      }
    });

    // Собираем итоговый URL
    let result = pathname;
    const queryString = urlParams.toString();
    if (queryString) {
      result += '?' + queryString;
    }
    if (hash) {
      result += '#' + hash;
    }

    return result;
  };

  const linkWithUTM = getInternalLinkWithUTM(to);

  return (
    <Link to={linkWithUTM} {...props}>
      {children}
    </Link>
  );
};

export default UTMLink;
