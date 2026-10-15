import exec from 'k6/execution';

import { baseUrl, envFlag, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runProcessOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l2_warm_burst';
const localRie = envFlag('LAMBDA_LOCAL_RIE', false);
const warmupRate = envInt('L2_WARMUP_RATE', smoke ? 2 : 5, 1);
const loadRate = envInt('L2_RATE', smoke ? 4 : 20, 1);
const warmupDuration = __ENV.L2_WARMUP_DURATION || (smoke ? '10s' : '2m');
const loadDuration = __ENV.L2_DURATION || (smoke ? '20s' : '10m');

const localScenario = smoke && localRie
	? {
		executor: 'shared-iterations',
		vus: 1,
		iterations: envInt('L2_LOCAL_ITERATIONS', 5, 1),
		maxDuration: __ENV.DURATION || '2m',
	}
	: null;

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: localScenario
		? {
				l2_warm_burst: localScenario,
			}
		: {
				l2_prewarm: {
					executor: 'constant-arrival-rate',
					exec: 'prewarm',
					rate: warmupRate,
					timeUnit: '1s',
					duration: warmupDuration,
					preAllocatedVUs: 2,
					maxVUs: 50,
					tags: { phase: 'warmup' },
				},
				l2_warm_burst: {
		executor: 'constant-arrival-rate',
					exec: 'load',
					rate: loadRate,
					timeUnit: '1s',
					duration: loadDuration,
					startTime: warmupDuration,
					preAllocatedVUs: 10,
					maxVUs: 120,
					tags: { phase: 'load' },
				},
			},
};

export function prewarm() {
	runProcessOrderOperation(baseUrl(), { phase: 'warmup', scenarioName });
}

export function load() {
	runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}

export default function l2WarmBurst() {
	const phase = exec.scenario.name === 'l2_prewarm' ? 'warmup' : 'load';
	runProcessOrderOperation(baseUrl(), { phase, scenarioName });
}
