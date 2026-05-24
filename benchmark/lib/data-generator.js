export const DEFAULT_BASE_URL = 'http://localhost:8081';
export const DEFAULT_SEED = 20260512;
export const DEFAULT_UUID_POOL_SIZE = 4096;

const STREETS = ['Rua das Flores', 'Avenida Brasil', 'Rua do Comercio', 'Alameda Central', 'Rua da Estacao'];
const CITIES = ['Lavras', 'Belo Horizonte', 'Sao Paulo', 'Campinas', 'Curitiba'];
const STATES = ['MG', 'MG', 'SP', 'SP', 'PR'];
const PRODUCT_NAMES = ['Mechanical Keyboard', 'Wireless Mouse', 'USB-C Hub', 'Notebook Stand', 'Noise Cancelling Headset'];

export function envFlag(name, fallback = false) {
  const value = __ENV[name];

  if (value === undefined || value === null || value === '') {
    return fallback;
  }

  return ['1', 'true', 'yes', 'on'].indexOf(String(value).toLowerCase()) >= 0;
}

export function envInt(name, fallback, minimum = 1) {
  const value = Number.parseInt(__ENV[name], 10);

  if (Number.isNaN(value) || value < minimum) {
    return fallback;
  }

  return value;
}

export function envNumber(name, fallback, minimum = 0) {
  const value = Number.parseFloat(__ENV[name]);

  if (Number.isNaN(value) || value < minimum) {
    return fallback;
  }

  return value;
}

export function isSmoke() {
  return envFlag('SMOKE', false);
}

export function baseUrl() {
  return String(__ENV.BASE_URL || DEFAULT_BASE_URL).replace(/\/+$/, '');
}

export function seed() {
  return envInt('SEED', DEFAULT_SEED, 1);
}

export function createPrng(initialSeed = DEFAULT_SEED) {
  let state = initialSeed >>> 0;

  return function next() {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function nextUint32(prng) {
  return Math.floor(prng() * 4294967296) >>> 0;
}

function hex(value, width) {
  return value.toString(16).padStart(width, '0').slice(-width);
}

function uuidFromPrng(prng) {
  const part1 = hex(nextUint32(prng), 8);
  const part2 = hex(nextUint32(prng), 4);
  const part3 = hex((nextUint32(prng) & 0x0fff) | 0x4000, 4);
  const part4 = hex((nextUint32(prng) & 0x3fff) | 0x8000, 4);
  const part5 = `${hex(nextUint32(prng), 8)}${hex(nextUint32(prng), 4)}`;

  return `${part1}-${part2}-${part3}-${part4}-${part5}`;
}

export function createUuidPool(size = DEFAULT_UUID_POOL_SIZE, initialSeed = DEFAULT_SEED) {
  const prng = createPrng(initialSeed);
  const pool = [];

  for (let index = 0; index < size; index += 1) {
    pool.push(uuidFromPrng(prng));
  }

  return pool;
}

export function uuidAt(pool, index) {
  return pool[Math.abs(index) % pool.length];
}

const SHARED_UUID_POOL = createUuidPool(envInt('UUID_POOL_SIZE', DEFAULT_UUID_POOL_SIZE, 128), seed());

export function uuidPool() {
  return SHARED_UUID_POOL;
}

export function moneyFromCents(cents) {
  return (cents / 100).toFixed(2);
}

export function dateRange(daysBack = 1, daysForward = 1) {
  const today = new Date();
  const from = new Date(today.getTime());
  const to = new Date(today.getTime());

  from.setUTCDate(from.getUTCDate() - daysBack);
  to.setUTCDate(to.getUTCDate() + daysForward);

  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

export function makeItemPayload(index, pool = uuidPool()) {
  const quantity = 1 + (index % 4);
  const cents = 999 + ((index * 137) % 5000);

  return {
    productId: uuidAt(pool, 1000 + index),
    productName: PRODUCT_NAMES[index % PRODUCT_NAMES.length],
    quantity,
    unitPrice: moneyFromCents(cents),
  };
}

export function makeProcessingItemPayload(index, pool = uuidPool()) {
  const quantity = 1 + (index % 4);
  const cents = 999 + ((index * 137) % 5000);

  return {
    productId: uuidAt(pool, 1000 + index),
    productName: PRODUCT_NAMES[index % PRODUCT_NAMES.length],
    quantity,
    unitPrice: Number(moneyFromCents(cents)),
  };
}

export function makeProcessingRequestPayload(index, options = {}) {
  const pool = options.uuidPool || uuidPool();
  const itemCount = options.itemCount || (1 + (index % 3));
  const items = [];
  let totalCents = 0;

  for (let itemIndex = 0; itemIndex < itemCount; itemIndex += 1) {
    const itemPayload = makeProcessingItemPayload(index * 10 + itemIndex, pool);
    totalCents += Math.round(Number(itemPayload.unitPrice) * 100) * itemPayload.quantity;
    items.push(itemPayload);
  }

  const addressIndex = index % CITIES.length;

  return {
    orderId: options.orderId || uuidAt(pool, 3000 + index),
    customerId: options.customerId || uuidAt(pool, index),
    items,
    shippingAddress: {
      zipCode: `3720${index % 10}-000`,
      state: STATES[addressIndex],
      city: CITIES[addressIndex],
    },
    totalAmount: Number(moneyFromCents(totalCents)),
  };
}

export function makeOrderPayload(index, options = {}) {
  const pool = options.uuidPool || uuidPool();
  const itemCount = options.itemCount || (1 + (index % 3));
  const items = [];

  for (let itemIndex = 0; itemIndex < itemCount; itemIndex += 1) {
    items.push(makeItemPayload(index * 10 + itemIndex, pool));
  }

  const addressIndex = index % STREETS.length;

  return {
    customerId: options.customerId || uuidAt(pool, index),
    discountAmount: options.discountAmount || (index % 5 === 0 ? '1.00' : '0.00'),
    items,
    shippingAddress: {
      zipCode: `3720${index % 10}-000`,
      street: STREETS[addressIndex],
      number: String(100 + (index % 900)),
      complement: index % 3 === 0 ? `Apto ${index % 50}` : null,
      city: CITIES[addressIndex],
      state: STATES[addressIndex],
    },
  };
}

export function statusForPendingOrder(index) {
  return index % 2 === 0 ? 'CONFIRMED' : 'CANCELLED';
}

export function thinkTimeSeconds(index, minimum = 0.5, maximum = 2) {
  const ratio = ((index * 37) % 1000) / 1000;
  return minimum + ((maximum - minimum) * ratio);
}
