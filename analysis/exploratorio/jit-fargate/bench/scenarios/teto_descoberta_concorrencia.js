import { baseUrl } from '../lib/data-generator.js';
import { runProcessOrderOperation } from '../lib/workload.js';

export const options = {
  scenarios: {
    teto_concorrencia: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 50,
      stages: [
        { target: 1, duration: '3m' },
        { target: 2, duration: '3m' },
        { target: 3, duration: '3m' },
        { target: 4, duration: '3m' },
        { target: 5, duration: '3m' },
        { target: 6, duration: '3m' },
      ],
    },
  },
};

export default function () {
  runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName: 'teto_descoberta_concorrencia' });
}
