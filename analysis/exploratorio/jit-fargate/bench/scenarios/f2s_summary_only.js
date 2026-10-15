import { baseUrl, envInt } from '../lib/data-generator.js';
import { benchmarkDataConfig, prepareOrderPools, runSummaryOperation } from '../lib/workload.js';

const RATE = envInt('F2S_RATE', 8, 1);

export const options = {
  scenarios: {
    f2s_summary_only: {
      executor: 'ramping-arrival-rate',
      startRate: 0,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 150,
      stages: [
        { target: RATE, duration: '30s' },
        { target: RATE, duration: '13m' },
        { target: 0,    duration: '30s' },
      ],
    },
  },
};

export function setup() {
  return prepareOrderPools(baseUrl(), benchmarkDataConfig(false));
}

export default function (data) {
  runSummaryOperation(baseUrl(), data, { phase: 'load', scenarioName: 'f2s_summary_only' });
}
