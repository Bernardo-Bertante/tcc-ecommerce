import { baseUrl, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runCreateOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l3_concurrency_burst';
const vus = envInt('L3_VUS', smoke ? 5 : 200, 1);

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: {
		l3_concurrency_burst: {
			executor: 'shared-iterations',
			vus,
			iterations: envInt('L3_ITERATIONS', vus, 1),
			maxDuration: __ENV.DURATION || (smoke ? '1m' : '5m'),
		},
	},
};

export default function l3ConcurrencyBurst() {
	runCreateOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}
