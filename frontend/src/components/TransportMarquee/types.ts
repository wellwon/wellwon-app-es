
export interface TransportType {
  Icon: React.ComponentType;
  type: 'truck' | 'ship' | 'train' | 'plane';
}

export interface TransportSequenceItem extends TransportType {
  delay: string;
}
