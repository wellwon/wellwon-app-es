
import { TruckIcon, TrainIcon, PlaneIcon, ShipIcon } from '../transport-icons';
import { TransportType, TransportSequenceItem } from './types';
import { TRANSPORT_CONFIG } from './constants';

export const createTransportSequence = (): TransportSequenceItem[] => {
  const transports: TransportType[] = [
    { Icon: TruckIcon, type: 'truck' },
    { Icon: ShipIcon, type: 'ship' },
    { Icon: TrainIcon, type: 'train' },
    { Icon: PlaneIcon, type: 'plane' }
  ];

  const sequence: TransportSequenceItem[] = [];
  const { TOTAL_DURATION, INSTANCES_PER_TRANSPORT } = TRANSPORT_CONFIG;
  const totalInstances = transports.length * INSTANCES_PER_TRANSPORT;
  const interval = TOTAL_DURATION / totalInstances;

  // Create array with multiple instances of each transport
  const transportPool: TransportType[] = [];
  transports.forEach(transport => {
    for (let i = 0; i < INSTANCES_PER_TRANSPORT; i++) {
      transportPool.push(transport);
    }
  });

  // Shuffle the array for randomization
  for (let i = transportPool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [transportPool[i], transportPool[j]] = [transportPool[j], transportPool[i]];
  }

  // Assign delays with larger intervals for reduced frequency
  transportPool.forEach((transport, index) => {
    sequence.push({
      ...transport,
      delay: `${index * interval}s`
    });
  });

  return sequence;
};

export const getTransportPosition = (type: string): string => {
  return TRANSPORT_CONFIG.POSITIONS[type as keyof typeof TRANSPORT_CONFIG.POSITIONS] || '10px';
};
