import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f3_burst_autoscaling';
const stages = smoke
	? [
		{ duration: '10s', target: envInt('F3_SMOKE_PEAK_RATE', 5, 1) },
		{ duration: '10s', target: 1 },
	]
	: [
		{ duration: '5m', target: 50 },
		{ duration: '2m', target: 500 },
		{ duration: '8m', target: 500 },
		{ duration: '5m', target: 50 },
	];

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f3_burst_autoscaling: {
			executor: 'ramping-arrival-rate',
			startRate: envInt('F3_START_RATE', smoke ? 1 : 50, 1),
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
