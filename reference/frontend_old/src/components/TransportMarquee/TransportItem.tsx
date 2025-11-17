
import { TransportSequenceItem } from './types';
import { getTransportPosition } from './utils';
import { TRANSPORT_CONFIG } from './constants';

interface TransportItemProps {
  transport: TransportSequenceItem;
  index: number;
}

const TransportItem = ({ transport, index }: TransportItemProps) => {
  const Icon = transport.Icon;
  const topPosition = getTransportPosition(transport.type);
  
  return (
    <div
      key={index}
      className="absolute animate-move-transport opacity-0"
      style={{
        animationDelay: transport.delay,
        animationDuration: TRANSPORT_CONFIG.ANIMATION_DURATION,
        animationIterationCount: 'infinite',
        animationTimingFunction: 'linear',
        top: topPosition,
        willChange: 'transform', // GPU оптимизация
        transform: 'translate3d(0, 0, 0)' // Принуждение к GPU слою
      }}
    >
      <Icon />
    </div>
  );
};

export default TransportItem;
