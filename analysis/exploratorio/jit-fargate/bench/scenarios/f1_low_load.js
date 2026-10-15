import { sleep } from 'k6';
import exec from 'k6/execution';

import { baseUrl, envInt, isSmoke, thinkTimeSeconds } from '../lib/data-generator.js';
import { FARGATE_THRESHOLDS, SMOKE_THRESHOLDS } from '../lib/thresholds.js';
import { benchmarkDataConfig, prepareOrderPools, runGeneralOrderOperation } from '../lib/workload.js';

const smoke = isSmoke();
const scenarioName = 'f1_low_load';

// F1_RATE é OBRIGATÓRIA em execução real (não-smoke) — sem default silencioso.
// Causa raiz do problema documentado em 08-known-problems.md: a coleta original de F1
// (analysis/fargate/fase3/f1-*) rodou no antigo default silencioso (30 iter/s) em vez da
// taxa pretendida (48 iter/s), porque a variável nunca foi passada na execução. Em smoke
// (SMOKE=true) mantém-se um valor baixo fixo, pois é apenas um teste de fiação.
function requiredF1Rate() {
	const raw = __ENV.F1_RATE;
	if (raw === undefined || raw === '') {
		throw new Error(
			'F1_RATE não definida — obrigatória, sem default. Passe -e F1_RATE=<iter/s> '
			+ '(taxa oficial de F1 = 48). Ver benchmark/run/f1_rerun.sh e 08-known-problems.md.',
		);
	}
	const parsed = Number.parseInt(raw, 10);
	if (Number.isNaN(parsed) || parsed < 1) {
		throw new Error(`F1_RATE inválida: "${raw}" — precisa ser um inteiro >= 1.`);
	}
	return parsed;
}

const rate = smoke ? envInt('F1_RATE', 2, 1) : requiredF1Rate();

export const options = {
	thresholds: smoke ? SMOKE_THRESHOLDS : FARGATE_THRESHOLDS,
	scenarios: {
		f1_low_load: {
			executor: 'ramping-arrival-rate',
			startRate: envInt('F1_START_RATE', smoke ? 1 : 1, 1),
			timeUnit: '1s',
			stages: smoke
				? [
					{ duration: __ENV.F1_RAMP_UP || '5s', target: rate },
					{ duration: __ENV.F1_DURATION || '20s', target: rate },
					{ duration: __ENV.F1_RAMP_DOWN || '5s', target: 0 },
				]
				: [
					{ duration: __ENV.F1_RAMP_UP || '2m', target: rate },
					{ duration: __ENV.F1_DURATION || '20m', target: rate },
					{ duration: __ENV.F1_RAMP_DOWN || '2m', target: 0 },
				],
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
