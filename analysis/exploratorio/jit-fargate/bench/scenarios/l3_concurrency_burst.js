import { baseUrl, envFlag, envInt, isSmoke } from '../lib/data-generator.js';
import { LAMBDA_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { runProcessOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'l3_concurrency_burst';
const localRie = envFlag('LAMBDA_LOCAL_RIE', false);
const warmRate = envInt('L3_WARMUP_RATE', smoke ? 5 : 20, 1);
const sustainRate = envInt('L3_RATE', smoke ? 12 : 100, 1);
const burstConcurrency = envInt('L3_BURST_CONCURRENCY', smoke ? 20 : 8, 1);
const warmupDuration = __ENV.L3_WARMUP_DURATION || (smoke ? '10s' : '2m');
const burstDuration = __ENV.L3_BURST_DURATION || '1s';
const sustainDuration = __ENV.L3_SUSTAIN_DURATION || (smoke ? '20s' : '5m');
const rampDownDuration = __ENV.L3_RAMP_DOWN || (smoke ? '8s' : '1m');

const localScenario = smoke && localRie
	? {
		executor: 'shared-iterations',
		vus: 1,
		iterations: envInt('L3_LOCAL_ITERATIONS', 12, 1),
		maxDuration: __ENV.DURATION || '2m',
	}
	: null;

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : LAMBDA_THRESHOLDS,
	scenarios: localScenario
		? {
				l3_concurrency_burst: localScenario,
			}
		: {
				l3_warmup: {
					executor: 'constant-arrival-rate',
					exec: 'warmup',
					rate: warmRate,
					timeUnit: '1s',
					duration: warmupDuration,
					preAllocatedVUs: 5,
					maxVUs: 80,
					tags: { phase: 'warmup' },
				},
				l3_burst: {
					executor: 'constant-vus',
					exec: 'burst',
					vus: burstConcurrency,
					duration: burstDuration,
					startTime: warmupDuration,
					tags: { phase: 'burst' },
				},
				l3_sustain: {
					executor: 'ramping-arrival-rate',
					exec: 'sustain',
					startRate: sustainRate,
					timeUnit: '1s',
					stages: [
						{ duration: sustainDuration, target: sustainRate },
						{ duration: rampDownDuration, target: warmRate },
					],
					startTime: warmupDuration,
					preAllocatedVUs: 20,
					maxVUs: 300,
					tags: { phase: 'load' },
				},
			},
};

export function warmup() {
	runProcessOrderOperation(baseUrl(), { phase: 'warmup', scenarioName });
}

export function burst() {
	runProcessOrderOperation(baseUrl(), { phase: 'burst', scenarioName });
}

export function sustain() {
	runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}

export default function l3ConcurrencyBurst() {
	runProcessOrderOperation(baseUrl(), { phase: 'load', scenarioName });
}
