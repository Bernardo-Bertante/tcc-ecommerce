import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f2_high_load';
const warmupRate = envInt('F2_WARMUP_RATE', smoke ? 2 : 30, 1);
const targetRate = envInt('F2_RATE', smoke ? 4 : 60, 1);
const prewarmDuration = __ENV.F2_PREWARM_DURATION || (smoke ? '10s' : '10m');
const rampUpDuration = __ENV.F2_RAMP_UP || (smoke ? '5s' : '3m');
const holdDuration = __ENV.F2_DURATION || (smoke ? '20s' : '30m');
const rampDownDuration = __ENV.F2_RAMP_DOWN || (smoke ? '5s' : '3m');

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f2_prewarm: {
			executor: 'constant-arrival-rate',
			exec: 'prewarm',
			rate: warmupRate,
			timeUnit: '1s',
			duration: prewarmDuration,
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 5 : 800, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 20 : 1500, 1),
			tags: { phase: 'warmup' },
		},
		f2_high_load: {
			executor: 'ramping-arrival-rate',
			exec: 'load',
			startRate: warmupRate,
			timeUnit: '1s',
			stages: [
				{ duration: rampUpDuration, target: targetRate },
				{ duration: holdDuration, target: targetRate },
				{ duration: rampDownDuration, target: 0 },
			],
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
