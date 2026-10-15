import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f3s_stress_300';
const rate = envInt('F3S_RATE', smoke ? 10 : 300, 1);

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f3s_stress_300: {
			executor: 'constant-arrival-rate',
			rate,
			timeUnit: '1s',
			duration: __ENV.F3S_DURATION || (smoke ? '20s' : '10m'),
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 10 : 1500, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 40 : 3000, 1),
			tags: { phase: 'load' },
		},
	},
};

export function setup() {
	return prepareOrderPools(baseUrl(), benchmarkDataConfig(smoke));
}

export default function f3sStress300(data) {
	runGeneralOrderOperation(baseUrl(), data, { phase: 'load', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}
