// Carga sustentada de processOrder (mesmo payload do L2) contra um container Lambda local (RIE).
import { runProcessOrderOperation } from 'file:///home/bernardo/Programming/ecommerce-tcc/benchmark/lib/workload.js';

const rate = Number(__ENV.RATE || 20);
const duration = __ENV.DURATION || '300s';

export const options = {
	scenarios: {
		load: {
			executor: 'constant-arrival-rate',
			rate,
			timeUnit: '1s',
			duration,
			// RIE não suporta invocações concorrentes (e um ambiente Lambda real também é serial).
			preAllocatedVUs: 1,
			maxVUs: 1,
		},
	},
};

export default function () {
	runProcessOrderOperation(__ENV.BASE_URL, { phase: 'load', scenarioName: 'cpuexp' });
}
