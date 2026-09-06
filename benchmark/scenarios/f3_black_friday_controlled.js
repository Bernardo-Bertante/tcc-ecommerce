import { load, setup } from './f2_high_load.js';
import { isSmoke } from '../lib/data-generator.js';

export { setup };

const numberEnv = (name, defaultValue) => {
  const raw = __ENV[name];

  if (raw === undefined || raw === '') {
    return defaultValue;
  }

  const parsed = Number(raw);

  if (Number.isFinite(parsed) === false) {
    throw new Error(`${name} must be numeric`);
  }

  return parsed;
};

const durationEnv = (name, defaultValue) => {
  return __ENV[name] || defaultValue;
};

const smoke = isSmoke();

// As tres taxas de F3 sao OBRIGATORIAS em execucao real (nao-smoke) — sem default silencioso.
// Mesmo motivo do fix em f1_low_load.js (08-known-problems.md): a coleta original de fase3
// passou as taxas por env vars efemeras nunca versionadas. F3 rodou correto (48/240/48), mas
// o F1 com o mesmo padrao caiu no default errado. Em smoke mantem-se um valor baixo fixo.
const requiredRate = (name) => {
  const raw = __ENV[name];

  if (raw === undefined || raw === '') {
    throw new Error(`${name} nao definida — obrigatoria em execucao real, sem default. `
      + `Passe -e ${name}=<iter/s> (taxas oficiais de F3: baseline 48 / pico 240 / recuperacao 48). `
      + 'Ver benchmark/run/f3_rerun.sh e 08-known-problems.md.');
  }

  const parsed = Number(raw);

  if (Number.isFinite(parsed) === false || parsed < 0) {
    throw new Error(`${name} invalida: "${raw}"`);
  }

  return parsed;
};

const BASELINE_RATE = smoke ? numberEnv('F3_BASELINE_RATE', 5) : requiredRate('F3_BASELINE_RATE');
const PEAK_RATE = smoke ? numberEnv('F3_PEAK_RATE', 20) : requiredRate('F3_PEAK_RATE');
const RECOVERY_RATE = smoke ? numberEnv('F3_RECOVERY_RATE', 8) : requiredRate('F3_RECOVERY_RATE');

export const options = {
  scenarios: {
    f3_black_friday_controlled: {
      executor: 'ramping-arrival-rate',
      startRate: BASELINE_RATE,
      timeUnit: '1s',
      preAllocatedVUs: numberEnv('PRE_ALLOCATED_VUS', 1500),
      maxVUs: numberEnv('MAX_VUS', 3000),
      stages: [
        { target: BASELINE_RATE, duration: durationEnv('F3_BASELINE_DURATION', '5m') },
        { target: PEAK_RATE, duration: durationEnv('F3_RAMP_UP_DURATION', '2m') },
        { target: PEAK_RATE, duration: durationEnv('F3_PEAK_DURATION', '10m') },
        { target: RECOVERY_RATE, duration: durationEnv('F3_RECOVERY_RAMP_DURATION', '2m') },
        { target: RECOVERY_RATE, duration: durationEnv('F3_RECOVERY_DURATION', '5m') },
        { target: 0, duration: durationEnv('F3_RAMP_DOWN_DURATION', '1m') },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{phase:load}': ['p(95)<2000', 'p(99)<5000'],
    checks: ['rate>0.99'],
  },
};

export default load;
