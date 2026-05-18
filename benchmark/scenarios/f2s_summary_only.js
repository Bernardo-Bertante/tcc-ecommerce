import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runSummaryOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f2s_summary_only';
const rate = envInt('F2S_RATE', smoke ? 2 : 50, 1);

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f2s_summary_only: {
			executor: 'constant-arrival-rate',
			rate,
			timeUnit: '1s',
			duration: __ENV.DURATION || (smoke ? '20s' : '5m'),
			preAllocatedVUs: envInt('PRE_ALLOCATED_VUS', smoke ? 5 : 120, 1),
			maxVUs: envInt('MAX_VUS', smoke ? 20 : 300, 1),
		},
	},
};

export function setup() {
	return prepareOrderPools(baseUrl(), benchmarkDataConfig(smoke));
}

export default function f2sSummaryOnly(data) {
	runSummaryOperation(baseUrl(), data, { phase: 'load', scenarioName });
	sleep(thinkTimeSeconds(exec.scenario.iterationInTest));
}
