import http from 'k6/http';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function base(baseUrl) {
  return String(baseUrl || '').replace(/\/+$/, '');
}

function query(params) {
  const parts = [];

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }

    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  });

  return parts.length === 0 ? '' : `?${parts.join('&')}`;
}

function tags(endpoint, extraTags = {}) {
  return Object.assign({ endpoint }, extraTags);
}

function jsonParams(endpoint, extraTags) {
  return {
    headers: JSON_HEADERS,
    tags: tags(endpoint, extraTags),
  };
}

function requestParams(endpoint, extraTags) {
  return {
    tags: tags(endpoint, extraTags),
  };
}

export function createOrder(baseUrl, payload, options = {}) {
  return http.post(`${base(baseUrl)}/orders`, JSON.stringify(payload), jsonParams('create_order', options.tags));
}

export function getOrder(baseUrl, id, options = {}) {
  return http.get(`${base(baseUrl)}/orders/${id}`, requestParams('get_order', options.tags));
}

export function getOrderHistory(baseUrl, id, options = {}) {
  return http.get(`${base(baseUrl)}/orders/${id}/history`, requestParams('get_order_history', options.tags));
}

export function getOrdersByCustomer(baseUrl, customerId, page = 0, size = 20, options = {}) {
  return http.get(
    `${base(baseUrl)}/orders/customer/${customerId}${query({ page, pageSize: size })}`,
    requestParams('get_orders_by_customer', options.tags),
  );
}

export function filterOrders(baseUrl, params = {}, options = {}) {
  const normalizedParams = Object.assign({}, params);

  if (normalizedParams.size !== undefined && normalizedParams.pageSize === undefined) {
    normalizedParams.pageSize = normalizedParams.size;
  }
  if (normalizedParams.from !== undefined && normalizedParams.fromDate === undefined) {
    normalizedParams.fromDate = normalizedParams.from;
  }
  if (normalizedParams.to !== undefined && normalizedParams.toDate === undefined) {
    normalizedParams.toDate = normalizedParams.to;
  }

  delete normalizedParams.size;
  delete normalizedParams.from;
  delete normalizedParams.to;

  return http.get(`${base(baseUrl)}/orders${query(normalizedParams)}`, requestParams('filter_orders', options.tags));
}

export function updateStatus(baseUrl, id, status, options = {}) {
  return http.put(
    `${base(baseUrl)}/orders/${id}/status`,
    JSON.stringify({ status }),
    jsonParams('update_status', options.tags),
  );
}

export function addItem(baseUrl, orderId, item, options = {}) {
  return http.post(`${base(baseUrl)}/orders/${orderId}/items`, JSON.stringify(item), jsonParams('add_item', options.tags));
}

export function removeItem(baseUrl, orderId, itemId, options = {}) {
  return http.del(`${base(baseUrl)}/orders/${orderId}/items/${itemId}`, null, requestParams('remove_item', options.tags));
}

export function cancelOrder(baseUrl, id, options = {}) {
  return http.del(`${base(baseUrl)}/orders/${id}`, null, requestParams('cancel_order', options.tags));
}

export function getSummary(baseUrl, from, to, options = {}) {
  return http.get(
    `${base(baseUrl)}/orders/summary${query({ fromDate: from, toDate: to })}`,
    requestParams('get_summary', options.tags),
  );
}

export function invokeReset(resetUrl, options = {}) {
  return http.post(resetUrl, null, requestParams('cold_reset', options.tags));
}
