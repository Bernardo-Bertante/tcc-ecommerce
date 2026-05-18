import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runCreateOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l2_warm_burst';
const warmupIterations = envInt('WARMUP_ITERATIONS', smoke ? 1 : 10, 0);

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: {
		l2_warm_burst: {
			executor: 'constant-arrival-rate',
			rate: 1,
			timeUnit: smoke ? '1s' : '3s',
			duration: __ENV.DURATION || (smoke ? '20s' : '30m'),
			preAllocatedVUs: 2,
			maxVUs: 10,
		},
	},
};

export default function l2WarmBurst() {
	const phase = exec.scenario.iterationInTest < warmupIterations ? 'warmup' : 'load';
	runCreateOrderOperation(baseUrl(), { phase, scenarioName });
}
