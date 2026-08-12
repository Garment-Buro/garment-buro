import type { HardwareVariant } from '../types.ts';
import { createRepeatedHardware } from '../utils/data.ts';

export const DEFAULT_DECORATION_CATALOG: HardwareVariant[] = [
    ...createRepeatedHardware('prints', 'Принт', 220, 92, 18, 64),
    ...createRepeatedHardware('rivets', 'Заклепка', 150, 38, 18, 38, 38, 38),
    ...createRepeatedHardware('distress', 'Дистресс', 120, 48, 18, 48),
    ...createRepeatedHardware('zippers', 'Молния', 180, 86, 18, 28),
    ...createRepeatedHardware('pullers', 'Пуллер', 140, 44, 18, 44),
    ...createRepeatedHardware('embroidery', 'Вышивка', 250, 80, 18, 80),
];
