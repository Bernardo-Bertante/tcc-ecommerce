import exec from 'k6/execution';

import { createOrder } from '../lib/endpoints.js';
import { expectCreatedOrder } from '../lib/checks.js';
import { baseUrl, envInt, isSmoke, makeOrderPayload } from '../lib/data-generator.js';

const smoke = isSmoke();
const orders = envInt('SEED_ORDERS', smoke ? 10 : 1000, 1);

export const options = {
	scenarios: {
		seed_orders: {
			executor: 'shared-iterations',
			vus: envInt('SEED_VUS', smoke ? 2 : 20, 1),
			iterations: orders,
			maxDuration: __ENV.DURATION || (smoke ? '1m' : '30m'),
		},
	},
};

export default function seedOrders() {
	const response = createOrder(baseUrl(), makeOrderPayload(exec.scenario.iterationInTest), {
		tags: { phase: 'seed', scenario: 'seed_orders', operation: 'create_order' },
	});

	expectCreatedOrder(response, 'seed create order');
}
