// Локальные типы для совместимости с старым кодом
export interface DealInfo {
  dealNumber: string;
  product: string;
  weight: number;
  volume: number;
  quantity: number;
  cost: number;
  deliveryTime: string;
  deliveryAddress: string;
  services: {
    name: string;
    cost: number;
    status: 'paid' | 'pending' | 'unpaid';
  }[];
  payments: {
    name: string;
    amount: number;
    status: 'paid' | 'pending' | 'unpaid';
    dueDate?: string;
  }[];
}

export interface OrderSummaryData {
  dealNumber: string;
  product: {
    name: string;
    price: number;
    quantity: number;
    supplier: string;
  };
  services: {
    category: string;
    items: {
      name: string;
      price: number;
      selected: boolean;
    }[];
  }[];
  payment: {
    method: string;
    total: number;
    currency: string;
  };
  delivery: {
    address: string;
    date: string;
    method: string;
  };
  totalCost: number;
}