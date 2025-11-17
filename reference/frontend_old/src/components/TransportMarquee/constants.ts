
export const TRANSPORT_CONFIG = {
  TOTAL_DURATION: 120, // Увеличили до 120 секунд
  INSTANCES_PER_TRANSPORT: 1, // Уменьшили до 1 экземпляра
  ANIMATION_DURATION: '120s', // Замедлили анимации
  POSITIONS: {
    truck: '9px',
    ship: '-5px', 
    train: '9.55px',
    plane: '10px'
  }
} as const;
