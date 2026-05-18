import { check } from 'k6';

export function parseJson(response) {
  try {
    return response.json();
  } catch (error) {
    return null;
  }
}

export function expectStatus(response, expectedStatus, name) {
  return check(response, {
    [`${name}: status ${expectedStatus}`]: (res) => res.status === expectedStatus,
  });
}

export function expectStatusRange(response, minimum, maximum, name) {
  return check(response, {
    [`${name}: status ${minimum}-${maximum - 1}`]: (res) => res.status >= minimum && res.status < maximum,
  });
}

export function expectCreatedOrder(response, name = 'create order') {
  const body = parseJson(response);

  return expectStatus(response, 201, name) && check(body, {
    [`${name}: response has id`]: (json) => json !== null && typeof json.id === 'string' && json.id.length > 0,
    [`${name}: response is pending`]: (json) => json !== null && json.status === 'PENDING',
    [`${name}: response has items`]: (json) => json !== null && Array.isArray(json.items) && json.items.length > 0,
  });
}

export function expectOrder(response, name = 'get order') {
  const body = parseJson(response);

  return expectStatus(response, 200, name) && check(body, {
    [`${name}: response has id`]: (json) => json !== null && typeof json.id === 'string' && json.id.length > 0,
    [`${name}: response has status`]: (json) => json !== null && typeof json.status === 'string' && json.status.length > 0,
  });
}

export function expectPagedOrders(response, name = 'paged orders') {
  const body = parseJson(response);

  return expectStatus(response, 200, name) && check(body, {
    [`${name}: response has content`]: (json) => json !== null && Array.isArray(json.content),
    [`${name}: response has page size`]: (json) => json !== null && typeof json.pageSize === 'number',
  });
}

export function expectSummary(response, name = 'summary') {
  const body = parseJson(response);

  return expectStatus(response, 200, name) && check(body, {
    [`${name}: response has totalOrders`]: (json) => json !== null && typeof json.totalOrders === 'number',
    [`${name}: response has totalRevenue`]: (json) => json !== null && json.totalRevenue !== undefined,
    [`${name}: response has ordersByStatus`]: (json) => json !== null && json.ordersByStatus !== undefined,
  });
}

export function requireCreatedOrder(response, name = 'setup create order') {
  if (!expectCreatedOrder(response, name)) {
    throw new Error(`${name} failed with status ${response.status}: ${response.body}`);
  }

  return parseJson(response);
}
