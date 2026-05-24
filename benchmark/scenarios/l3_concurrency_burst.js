import { baseUrl, envFlag, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runProcessOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l3_concurrency_burst';
const localRie = envFlag('LAMBDA_LOCAL_RIE', false);
const vus = envInt('L3_VUS', smoke && localRie ? 1 : (smoke ? 5 : 200), 1);

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
	runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}
