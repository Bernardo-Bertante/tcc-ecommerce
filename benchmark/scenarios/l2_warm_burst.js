import exec from 'k6/execution';

import { baseUrl, envFlag, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runProcessOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l2_warm_burst';
const warmupIterations = envInt('WARMUP_ITERATIONS', smoke ? 1 : 10, 0);
const localRie = envFlag('LAMBDA_LOCAL_RIE', false);
const l2Scenario = smoke && localRie
	? {
		executor: 'shared-iterations',
		vus: 1,
		iterations: envInt('L2_LOCAL_ITERATIONS', 5, 1),
		maxDuration: __ENV.DURATION || '2m',
	}
	: {
		executor: 'constant-arrival-rate',
		rate: 1,
		timeUnit: smoke ? '1s' : '3s',
		duration: __ENV.DURATION || (smoke ? '20s' : '30m'),
		preAllocatedVUs: 2,
		maxVUs: 10,
	};

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: {
		l2_warm_burst: l2Scenario,
	},
};

export default function l2WarmBurst() {
	const phase = exec.scenario.iterationInTest < warmupIterations ? 'warmup' : 'load';
	runProcessOrderOperation(baseUrl(), { phase, scenarioName });
}
