import exec from 'k6/execution';

import { createOrder, getOrder, getOrdersByCustomer, getSummary, updateStatus } from './endpoints.js';
import { invokeProcessor } from './lambda-invoker.js';
import { expectCreatedOrder, expectOrder, expectPagedOrders, expectProcessingResult, expectStatus, expectSummary, requireCreatedOrder } from './checks.js';
import { dateRange, envInt, makeOrderPayload, makeProcessingRequestPayload, statusForPendingOrder, uuidAt, uuidPool } from './data-generator.js';

export function benchmarkDataConfig(smoke) {
  return {
    readPoolSize: envInt('READ_POOL_SIZE', smoke ? 6 : 120, 1),
    customerPoolSize: envInt('CUSTOMER_POOL_SIZE', smoke ? 3 : 30, 1),
    pageSize: envInt('PAGE_SIZE', 20, 1),
  };
}

export function prepareOrderPools(baseUrl, config = {}) {
  const pool = uuidPool();
  const customerPoolSize = config.customerPoolSize || 3;
  const readPoolSize = config.readPoolSize || 6;
  const pageSize = config.pageSize || 20;
  const customers = [];
  const readOrders = [];
  const range = dateRange(1, 1);

  for (let index = 0; index < customerPoolSize; index += 1) {
    customers.push(uuidAt(pool, index));
  }

  for (let index = 0; index < readPoolSize; index += 1) {
    const payload = makeOrderPayload(index, {
      uuidPool: pool,
      customerId: customers[index % customers.length],
    });
    const response = createOrder(baseUrl, payload, {
      tags: { phase: 'setup', operation: 'seed_order' },
    });
    const order = requireCreatedOrder(response, 'setup seed order');
    readOrders.push(order.id);
  }

  return {
    customers,
    readOrders,
    range,
    pageSize,
  };
}

function operationTags(phase, scenarioName, operation) {
  return {
    phase,
    scenario: scenarioName,
    operation,
  };
}

export function runGeneralOrderOperation(baseUrl, data, options = {}) {
  const iteration = exec.scenario.iterationInTest;
  const slot = iteration % 100;
  const phase = options.phase || 'load';
  const scenarioName = options.scenarioName || exec.scenario.name;

  if (slot < 51) {
    const orderId = data.readOrders[iteration % data.readOrders.length];
    const response = getOrder(baseUrl, orderId, {
      tags: operationTags(phase, scenarioName, 'get_order'),
    });
    expectOrder(response, 'get order');
    return;
  }

  if (slot < 71) {
    const response = createOrder(baseUrl, makeOrderPayload(iteration + 5000), {
      tags: operationTags(phase, scenarioName, 'create_order'),
    });
    expectCreatedOrder(response, 'create order');
    return;
  }

  if (slot < 86) {
    const customerId = data.customers[iteration % data.customers.length];
    const response = getOrdersByCustomer(baseUrl, customerId, 0, data.pageSize, {
      tags: operationTags(phase, scenarioName, 'get_orders_by_customer'),
    });
    expectPagedOrders(response, 'get orders by customer');
    return;
  }

  if (slot < 98) {
    const createResponse = createOrder(baseUrl, makeOrderPayload(iteration + 10000), {
      tags: operationTags('auxiliary', scenarioName, 'create_order_for_status_update'),
    });
    const order = requireCreatedOrder(createResponse, 'create order for status update');
    const response = updateStatus(baseUrl, order.id, statusForPendingOrder(iteration), {
      tags: operationTags(phase, scenarioName, 'update_status'),
    });
    expectStatus(response, 200, 'update status');
    return;
  }

  const response = getSummary(baseUrl, data.range.from, data.range.to, {
    tags: operationTags(phase, scenarioName, 'get_summary'),
  });
  expectSummary(response, 'get summary');
}

export function runSummaryOperation(baseUrl, data, options = {}) {
  const phase = options.phase || 'load';
  const scenarioName = options.scenarioName || exec.scenario.name;
  const response = getSummary(baseUrl, data.range.from, data.range.to, {
    tags: operationTags(phase, scenarioName, 'get_summary'),
  });

  expectSummary(response, 'get summary');
}

export function runCreateOrderOperation(baseUrl, options = {}) {
  const iteration = exec.scenario.iterationInTest;
  const phase = options.phase || 'load';
  const scenarioName = options.scenarioName || exec.scenario.name;
  const response = createOrder(baseUrl, makeOrderPayload(iteration + 20000), {
    tags: operationTags(phase, scenarioName, 'create_order'),
  });

  expectCreatedOrder(response, 'create order');
}

export function runProcessOrderOperation(baseUrl, options = {}) {
  const iteration = exec.scenario.iterationInTest;
  const phase = options.phase || 'load';
  const scenarioName = options.scenarioName || exec.scenario.name;
  const response = invokeProcessor(baseUrl, makeProcessingRequestPayload(iteration + 20000), {
    tags: operationTags(phase, scenarioName, 'process_order'),
  });

  expectProcessingResult(response, 'process order');
}
