import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f1_low_load';
const rate = envInt('F1_RATE', smoke ? 2 : 30, 1);

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f1_low_load: {
			executor: 'constant-arrival-rate',
			rate,
			timeUnit: '1s',
			duration: __ENV.DURATION || (smoke ? '20s' : '10m'),
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 5 : 80, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 20 : 200, 1),
		},
	},
};

export function setup() {
	return prepareOrderPools(baseUrl(), benchmarkDataConfig(smoke));
}

export default function f1LowLoad(data) {
	runGeneralOrderOperation(baseUrl(), data, { phase: 'load', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}
