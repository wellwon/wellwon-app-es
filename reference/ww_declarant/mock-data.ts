/**
 * Mock Data for TestApp - Тестовые данные для дизайн-системы
 */

import { CheckCircle, Clock, AlertCircle } from 'lucide-react';
import type { BatchData, StatsData, SelectOption, DocumentItem } from './types';

/**
 * Мок-данные для статистики
 */
export const mockStats: StatsData = {
  total_batches: 6,
  completed_batches: 5,
  processing_batches: 0,
  total_documents: 55,
};

/**
 * Мок-данные для таблицы деклараций
 */
export const mockBatches: BatchData[] = [
  { id: '1', number: 'FTS-00104', status: 'completed', docs: '3/3', extracts: 3, date: '21 нояб. 2025, 11:25', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '2', number: 'FTS-00103', status: 'completed', docs: '4/4', extracts: 4, date: '14 нояб. 2025, 11:42', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '3', number: 'FTS-00102', status: 'error', docs: '0/3', extracts: 0, date: '09 нояб. 2025, 17:19', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '4', number: 'FTS-00101', status: 'completed', docs: '3/3', extracts: 3, date: '09 нояб. 2025, 17:15', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '5', number: 'FTS-00100', status: 'completed', docs: '3/3', extracts: 3, date: '09 нояб. 2025, 09:58', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '6', number: 'FTS-00099', status: 'completed', docs: '3/3', extracts: 3, date: '09 нояб. 2025, 09:18', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '7', number: 'FTS-00098', status: 'processing', docs: '2/3', extracts: 2, date: '08 нояб. 2025, 16:30', icon: Clock, iconColor: 'text-accent-yellow', statusText: 'В обработке' },
  { id: '8', number: 'FTS-00097', status: 'completed', docs: '5/5', extracts: 5, date: '08 нояб. 2025, 14:22', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '9', number: 'FTS-00096', status: 'completed', docs: '3/3', extracts: 3, date: '07 нояб. 2025, 10:15', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '10', number: 'FTS-00095', status: 'error', docs: '0/4', extracts: 0, date: '06 нояб. 2025, 18:45', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '11', number: 'FTS-00094', status: 'completed', docs: '2/2', extracts: 2, date: '06 нояб. 2025, 12:30', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '12', number: 'FTS-00093', status: 'completed', docs: '4/4', extracts: 4, date: '05 нояб. 2025, 16:10', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '13', number: 'FTS-00092', status: 'completed', docs: '3/3', extracts: 3, date: '05 нояб. 2025, 09:25', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '14', number: 'FTS-00091', status: 'processing', docs: '1/3', extracts: 1, date: '04 нояб. 2025, 15:40', icon: Clock, iconColor: 'text-accent-yellow', statusText: 'В обработке' },
  { id: '15', number: 'FTS-00090', status: 'completed', docs: '3/3', extracts: 3, date: '04 нояб. 2025, 11:55', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '16', number: 'FTS-00089', status: 'completed', docs: '5/5', extracts: 5, date: '03 нояб. 2025, 17:20', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '17', number: 'FTS-00088', status: 'completed', docs: '3/3', extracts: 3, date: '03 нояб. 2025, 10:05', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '18', number: 'FTS-00087', status: 'error', docs: '0/2', extracts: 0, date: '02 нояб. 2025, 14:15', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '19', number: 'FTS-00086', status: 'completed', docs: '4/4', extracts: 4, date: '02 нояб. 2025, 08:50', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '20', number: 'FTS-00085', status: 'completed', docs: '3/3', extracts: 3, date: '01 нояб. 2025, 16:30', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '21', number: 'FTS-00084', status: 'completed', docs: '2/2', extracts: 2, date: '01 нояб. 2025, 13:45', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '22', number: 'FTS-00083', status: 'processing', docs: '2/4', extracts: 2, date: '31 окт. 2025, 15:20', icon: Clock, iconColor: 'text-accent-yellow', statusText: 'В обработке' },
  { id: '23', number: 'FTS-00082', status: 'completed', docs: '3/3', extracts: 3, date: '31 окт. 2025, 09:10', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '24', number: 'FTS-00081', status: 'completed', docs: '5/5', extracts: 5, date: '30 окт. 2025, 17:55', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '25', number: 'FTS-00080', status: 'completed', docs: '3/3', extracts: 3, date: '30 окт. 2025, 11:40', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '26', number: 'FTS-00079', status: 'error', docs: '0/3', extracts: 0, date: '29 окт. 2025, 14:25', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '27', number: 'FTS-00078', status: 'completed', docs: '4/4', extracts: 4, date: '29 окт. 2025, 08:15', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '28', number: 'FTS-00077', status: 'completed', docs: '3/3', extracts: 3, date: '28 окт. 2025, 16:50', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '29', number: 'FTS-00076', status: 'completed', docs: '2/2', extracts: 2, date: '28 окт. 2025, 12:35', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '30', number: 'FTS-00075', status: 'completed', docs: '3/3', extracts: 3, date: '27 окт. 2025, 15:10', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '31', number: 'FTS-00074', status: 'processing', docs: '1/2', extracts: 1, date: '27 окт. 2025, 09:45', icon: Clock, iconColor: 'text-accent-yellow', statusText: 'В обработке' },
  { id: '32', number: 'FTS-00073', status: 'completed', docs: '4/4', extracts: 4, date: '26 окт. 2025, 17:20', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '33', number: 'FTS-00072', status: 'completed', docs: '3/3', extracts: 3, date: '26 окт. 2025, 11:05', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '34', number: 'FTS-00071', status: 'completed', docs: '5/5', extracts: 5, date: '25 окт. 2025, 14:40', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '35', number: 'FTS-00070', status: 'error', docs: '0/3', extracts: 0, date: '25 окт. 2025, 08:25', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '36', number: 'FTS-00069', status: 'completed', docs: '3/3', extracts: 3, date: '24 окт. 2025, 16:10', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '37', number: 'FTS-00068', status: 'completed', docs: '2/2', extracts: 2, date: '24 окт. 2025, 12:55', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '38', number: 'FTS-00067', status: 'completed', docs: '4/4', extracts: 4, date: '23 окт. 2025, 15:30', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '39', number: 'FTS-00066', status: 'processing', docs: '2/3', extracts: 2, date: '23 окт. 2025, 09:15', icon: Clock, iconColor: 'text-accent-yellow', statusText: 'В обработке' },
  { id: '40', number: 'FTS-00065', status: 'completed', docs: '3/3', extracts: 3, date: '22 окт. 2025, 17:40', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '41', number: 'FTS-00064', status: 'completed', docs: '3/3', extracts: 3, date: '22 окт. 2025, 11:25', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '42', number: 'FTS-00063', status: 'completed', docs: '5/5', extracts: 5, date: '21 окт. 2025, 14:10', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '43', number: 'FTS-00062', status: 'error', docs: '0/2', extracts: 0, date: '21 окт. 2025, 08:55', icon: AlertCircle, iconColor: 'text-accent-red', statusText: 'Ошибка' },
  { id: '44', number: 'FTS-00061', status: 'completed', docs: '4/4', extracts: 4, date: '20 окт. 2025, 16:30', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
  { id: '45', number: 'FTS-00060', status: 'completed', docs: '3/3', extracts: 3, date: '20 окт. 2025, 10:15', icon: CheckCircle, iconColor: 'text-accent-green', statusText: 'Завершено' },
];

/**
 * Таможенные процедуры для импорта (ИМ)
 */
export const customsProceduresIM: SelectOption[] = [
  { value: '40', label: '40 - Выпуск для внутреннего потребления' },
  { value: '41', label: '41 - Свободная таможенная зона' },
  { value: '42', label: '42 - Переработка на таможенной территории' },
  { value: '51', label: '51 - Переработка вне таможенной территории' },
  { value: '53', label: '53 - Временный ввоз (допуск)' },
  { value: '63', label: '63 - Реимпорт' },
  { value: '78', label: '78 - Уничтожение' },
];

/**
 * Таможенные процедуры для экспорта (ЭК)
 */
export const customsProceduresEK: SelectOption[] = [
  { value: '10', label: '10 - Экспорт' },
  { value: '21', label: '21 - Реэкспорт' },
  { value: '22', label: '22 - Временный вывоз' },
  { value: '23', label: '23 - Переработка вне таможенной территории' },
  { value: '31', label: '31 - Свободная таможенная зона' },
  { value: '78', label: '78 - Уничтожение' },
];

/**
 * Особенности декларирования
 */
export const featuresData: SelectOption[] = [
  { value: 'none', label: 'Без особенностей' },
  { value: 'auto', label: 'АВ - Автомобили' },
  { value: 'alcohol', label: 'АЛ - Алкогольная продукция' },
  { value: 'tobacco', label: 'ТБ - Табачная продукция' },
  { value: 'food', label: 'ПП - Пищевая продукция' },
  { value: 'medicine', label: 'ЛС - Лекарственные средства' },
];

/**
 * Виды перемещения для транзита (ТТ)
 */
export const transitTypesData: SelectOption[] = [
  { value: '80', label: '80 - Таможенный транзит' },
  { value: '81', label: '81 - Таможенный транзит (ТС)' },
  { value: '82', label: '82 - Международный транзит' },
  { value: '83', label: '83 - Внутренний транзит' },
];

/**
 * Особенности перемещения для транзита (ТТ)
 */
export const transitFeaturesData: SelectOption[] = [
  { value: 'none', label: 'Без особенностей' },
  { value: 'dangerous', label: 'ОГ - Опасные грузы' },
  { value: 'oversized', label: 'НГ - Негабаритные грузы' },
  { value: 'perishable', label: 'СП - Скоропортящиеся грузы' },
  { value: 'valuable', label: 'ЦГ - Ценные грузы' },
];

/**
 * Таможенные органы
 */
export const customsOfficesData: SelectOption[] = [
  { value: 'central', label: '10000000 - Центральная акцизная таможня' },
  { value: 'moscow', label: '10129000 - Московская областная таможня' },
  { value: 'sheremetyevo', label: '10005000 - Шереметьевская таможня' },
  { value: 'domodedovo', label: '10002000 - Домодедовская таможня' },
  { value: 'vnukovo', label: '10001000 - Внуковская таможня' },
  { value: 'baltiysk', label: '10216000 - Балтийская таможня' },
  { value: 'spb', label: '10210000 - Санкт-Петербургская таможня' },
];

/**
 * Организации
 */
export const organizationsData: SelectOption[] = [
  { value: 'promtorg', label: 'ООО "Промторг"' },
  { value: 'techimport', label: 'ООО "ТехИмпорт"' },
  { value: 'euroservice', label: 'АО "ЕвроСервис"' },
  { value: 'globallogistics', label: 'ООО "Глобал Логистикс"' },
  { value: 'transsnab', label: 'ЗАО "ТрансСнаб"' },
];

/**
 * Декларанты
 */
export const declarantsData: SelectOption[] = [
  { value: 'ivanov', label: 'Иванов Иван Иванович' },
  { value: 'petrov', label: 'Петров Пётр Петрович' },
  { value: 'sidorov', label: 'Сидоров Сидор Сидорович' },
  { value: 'kuznetsova', label: 'Кузнецова Мария Александровна' },
  { value: 'sokolova', label: 'Соколова Анна Викторовна' },
];

/**
 * Основные документы (старый формат - для совместимости)
 */
export const mainDocuments: DocumentItem[] = [
  { id: '1', name: 'Декларация на товары', status: 'Ожидает проверки', statusColor: 'text-accent-yellow', hasLink: true },
  { id: '2', name: 'Таможенная расписка', status: 'Заполнено', statusColor: 'text-accent-green', hasLink: false },
  { id: '3', name: 'Опись документов', status: 'Не заполнено', statusColor: 'text-gray-400', hasLink: false },
];

/**
 * Основные документы для ИМ/ЭК (создание декларации)
 */
export const mainDocumentsIMEK: DocumentItem[] = [
  { id: '1', name: 'Декларация на товары', status: 'Не заполнено', statusColor: 'text-accent-red', hasLink: true },
];

/**
 * Основные документы для ТТ (транзит)
 */
export const mainDocumentsTT: DocumentItem[] = [
  { id: '1', name: 'Транзитная декларация', status: 'Не заполнено', statusColor: 'text-accent-red', hasLink: false },
];

/**
 * Пункты меню "Добавить" для ИМ/ЭК
 */
export const addMenuItemsIMEK = [
  'ДТС-3',
  'ДТС-4',
  'Декларирование в нерабочее время',
  'Карточка транспортного средства',
];

/**
 * Пункты меню "Добавить" для ТТ
 */
export const addMenuItemsTT = [
  'Декларирование в нерабочее время',
];

/**
 * Документы по товарам (графа 44)
 */
export const goodsDocuments: DocumentItem[] = [
  {
    id: '1',
    type: 'Контракт',
    code: '03011/0',
    number: 'RU-CN-2018/156',
    date: '15 декабря 2018',
    linkedGoods: 3,
    archived: true,
    presentedWithDT: false
  },
  {
    id: '2',
    type: 'Спецификация к контракту',
    code: '03012/0',
    number: 'SPEC-156/RU-01',
    date: '20 декабря 2018',
    linkedGoods: 3,
    archived: false,
    presentedWithDT: false
  },
  {
    id: '3',
    type: 'Инвойс',
    code: '04021/0',
    number: 'IN-156/RU-12',
    date: '27 декабря 2018',
    linkedGoods: 1,
    archived: true,
    presentedWithDT: false
  }
];

/**
 * Регистрационные документы (графа 44)
 */
export const registrationDocuments: DocumentItem[] = [
  {
    id: '1',
    type: 'Свидетельство о государственной регистрации юридического лица',
    code: '04011/0',
    number: '60 00554457',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '2',
    type: 'Устав',
    code: '04011/0',
    number: 'б/н',
    date: '4 июля 2010',
    archived: false,
    presentedWithDT: false
  },
  {
    id: '3',
    type: 'Выписка из приказа о назначении на должность единоличного исполнительного органа организации',
    code: '04011/0',
    number: '1-K',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '4',
    type: 'Свидетельство о постановке на учет в налоговом органе',
    code: '04011/0',
    number: '60 00554460',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '5',
    type: 'Трудовой договор',
    code: '04011/0',
    number: '1',
    date: '4 июля 2010',
    archived: false,
    presentedWithDT: false
  },
  {
    id: '6',
    type: 'Паспорт гражданина РФ',
    code: '09023/0',
    number: '4504 №452188',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
  {
    id: '7',
    type: 'Решение единственного учредителя',
    code: '04011/0',
    number: '1',
    date: '4 июля 2010',
    archived: true,
    presentedWithDT: false
  },
];
