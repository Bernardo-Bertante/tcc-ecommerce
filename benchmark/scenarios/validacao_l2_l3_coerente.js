import { baseUrl } from '../lib/data-generator.js';
import { runProcessOrderOperation } from '../lib/workload.js';

export const options = {
  scenarios: {
    validacao: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { target: 31, duration: '30s' },   // ramp até taxa de L2
        { target: 31, duration: '4m' },    // platô L2 (validação)
        { target: 77, duration: '30s' },   // ramp até taxa de L3
        { target: 77, duration: '4m' },    // platô L3 (validação)
        { target: 0,  duration: '30s' },
      ],
    },
  },
};

export default function () {
  runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName: 'validacao_l2_l3_coerente' });
}
