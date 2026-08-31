import { baseUrl, envFlag, envInt, isSmoke } from '../lib/data-generator.js';
import { invokeReset } from '../lib/lambda-invoker.js';
import { expectStatusRange } from '../lib/checks.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runProcessOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l1_sparse_coldstart';
const singleInvocation = envFlag('L1_SINGLE_INVOCATION', false);
const localRie = envFlag('LAMBDA_LOCAL_RIE', false);

if (envFlag('REQUIRE_COLD_RESET', false) && !__ENV.RESET_URL) {
	throw new Error('L1 cold-start scenario requires RESET_URL when REQUIRE_COLD_RESET=true.');
}

const sparseScenario = singleInvocation || (smoke && localRie)
	? {
		executor: 'shared-iterations',
		vus: 1,
		iterations: envInt('L1_LOCAL_ITERATIONS', 1, 1),
		maxDuration: '2m',
	}
	: {
		executor: 'constant-arrival-rate',
		rate: 1,
		timeUnit: smoke ? '5s' : '15m',
		duration: __ENV.DURATION || (smoke ? '40s' : '150m'),
		preAllocatedVUs: 1,
		maxVUs: 1,
	};

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: {
		l1_sparse_coldstart: sparseScenario,
	},
};

export default function l1SparseColdstart() {
	if (__ENV.RESET_URL) {
		const resetResponse = invokeReset(__ENV.RESET_URL, {
			tags: { phase: 'reset', scenario: scenarioName, operation: 'cold_reset' },
		});
		expectStatusRange(resetResponse, 200, 300, 'cold reset');
	}

	runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}
