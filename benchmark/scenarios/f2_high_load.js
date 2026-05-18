import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f2_high_load';
const rate = envInt('F2_RATE', smoke ? 2 : 300, 1);
const prewarmDuration = __ENV.F2_PREWARM_DURATION || (smoke ? '10s' : '10m');
const loadDuration = __ENV.DURATION || __ENV.F2_DURATION || (smoke ? '20s' : '30m');

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f2_prewarm: {
			executor: 'constant-arrival-rate',
			exec: 'prewarm',
			rate,
			timeUnit: '1s',
			duration: prewarmDuration,
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 5 : 800, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 20 : 1500, 1),
			tags: { phase: 'warmup' },
		},
		f2_high_load: {
			executor: 'constant-arrival-rate',
			exec: 'load',
			rate,
			timeUnit: '1s',
			duration: loadDuration,
			startTime: prewarmDuration,
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 5 : 800, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 20 : 1500, 1),
			tags: { phase: 'load' },
		},
	},
};

export function setup() {
	return prepareOrderPools(baseUrl(), benchmarkDataConfig(smoke));
}

export function prewarm(data) {
	runGeneralOrderOperation(baseUrl(), data, { phase: 'warmup', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}

export function load(data) {
	runGeneralOrderOperation(baseUrl(), data, { phase: 'load', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}

export default function f2HighLoad(data) {
	load(data);
}
