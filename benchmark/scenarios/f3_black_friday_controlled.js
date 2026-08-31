import { load, setup } from './f2_high_load.js';

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

const BASELINE_RATE = numberEnv('F3_BASELINE_RATE', 30);
const PEAK_RATE = numberEnv('F3_PEAK_RATE', 300);
const RECOVERY_RATE = numberEnv('F3_RECOVERY_RATE', 60);

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
