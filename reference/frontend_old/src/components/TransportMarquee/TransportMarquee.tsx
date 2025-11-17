
import { memo, useMemo } from 'react';
import { createTransportSequence } from './utils';
import TransportItem from './TransportItem';
import CentralLine from './CentralLine';
import DecorativeDots from './DecorativeDots';
import { usePageVisibility } from '@/hooks/usePageVisibility';

const TransportMarquee = memo(() => {
  const isVisible = usePageVisibility();
  const transportIcons = useMemo(() => createTransportSequence(), []);

  return (
    <section className="relative overflow-hidden py-[12px]">
      <CentralLine />
      
      {/* Moving icons - приостанавливаем анимации при неактивной вкладке */}
      <div 
        className="relative h-20 flex items-center" 
        style={{ 
          animationPlayState: isVisible ? 'running' : 'paused',
        }}
      >
        {transportIcons.map((transport, index) => (
          <TransportItem 
            key={index}
            transport={transport}
            index={index}
          />
        ))}
      </div>
      
      <DecorativeDots />
    </section>
  );
});

TransportMarquee.displayName = 'TransportMarquee';

export default TransportMarquee;
