import { sleep } from 'k6';
import { baseUrl } from '../lib/data-generator.js';
import { benchmarkDataConfig, prepareOrderPools, runSummaryOperation } from '../lib/workload.js';

export const options = {
  scenarios: {
    teto_summary: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 300,
      stages: [
        { target: 2,  duration: '3m' },
        { target: 5,  duration: '3m' },
        { target: 8,  duration: '3m' },
        { target: 12, duration: '3m' },
        { target: 16, duration: '3m' },
        { target: 20, duration: '3m' },
      ],
    },
  },
};

export function setup() {
  return prepareOrderPools(baseUrl(), benchmarkDataConfig(false));
}

export default function (data) {
  runSummaryOperation(baseUrl(), data, { phase: 'load', scenarioName: 'teto_descoberta_summary' });
  sleep(1);
}
