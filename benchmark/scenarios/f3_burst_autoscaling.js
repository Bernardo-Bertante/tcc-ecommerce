import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f3_burst_autoscaling';
const baselineRate = envInt('F3_BASELINE_RATE', smoke ? 3 : 30, 1);
const averageBlackFridayRate = envInt('F3_AVERAGE_RATE', smoke ? 12 : 225, 1);
const stressRate = envInt('F3_STRESS_RATE', smoke ? 20 : 300, 1);
const stages = smoke
	? [
		{ duration: __ENV.F3_BASELINE_DURATION || '8s', target: baselineRate },
		{ duration: __ENV.F3_RAMP_UP_TO_AVERAGE || '8s', target: averageBlackFridayRate },
		{ duration: __ENV.F3_AVERAGE_DURATION || '12s', target: averageBlackFridayRate },
		{ duration: __ENV.F3_RAMP_UP_TO_STRESS || '6s', target: stressRate },
		{ duration: __ENV.F3_STRESS_DURATION || '12s', target: stressRate },
		{ duration: __ENV.F3_RAMP_DOWN || '8s', target: baselineRate },
	]
	: [
		{ duration: __ENV.F3_BASELINE_DURATION || '5m', target: baselineRate },
		{ duration: __ENV.F3_RAMP_UP_TO_AVERAGE || '3m', target: averageBlackFridayRate },
		{ duration: __ENV.F3_AVERAGE_DURATION || '10m', target: averageBlackFridayRate },
		{ duration: __ENV.F3_RAMP_UP_TO_STRESS || '2m', target: stressRate },
		{ duration: __ENV.F3_STRESS_DURATION || '10m', target: stressRate },
		{ duration: __ENV.F3_RAMP_DOWN || '3m', target: baselineRate },
	];

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f3_burst_autoscaling: {
			executor: 'ramping-arrival-rate',
			startRate: envInt('F3_START_RATE', smoke ? 1 : baselineRate, 1),
			timeUnit: '1s',
			stages,
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 10 : 1200, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 40 : 2500, 1),
		},
	},
};

export function setup() {
	return prepareOrderPools(baseUrl(), benchmarkDataConfig(smoke));
}

export default function f3BurstAutoscaling(data) {
	runGeneralOrderOperation(baseUrl(), data, { phase: 'load', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}
