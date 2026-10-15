import { sleep } from 'k6';
import { baseUrl } from '../lib/data-generator.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

export const options = {
  scenarios: {
    teto: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 2000,
      maxVUs: 4000,
      stages: [
        { target: 100, duration: '3m' },
        { target: 150, duration: '3m' },
        { target: 200, duration: '3m' },
        { target: 250, duration: '3m' },
        { target: 300, duration: '3m' },
        { target: 350, duration: '3m' },
        { target: 400, duration: '3m' },
      ],
    },
  },
};

export function setup() {
  return prepareOrderPools(baseUrl(), benchmarkDataConfig(false));
}

export default function (data) {
  runGeneralOrderOperation(baseUrl(), data, { phase: 'load', scenarioName: 'teto_descoberta' });
  sleep(1);
}
