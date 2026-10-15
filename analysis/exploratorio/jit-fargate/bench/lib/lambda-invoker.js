import http from 'k6/http';

import { envFlag } from './data-generator.js';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function base(baseUrl) {
  return String(baseUrl || '').replace(/\/+$/, '');
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

function looksLikeLocalLambda(baseUrl) {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:[0-9]+)?($|\/)/.test(baseUrl);
}

export function lambdaInvokeUrl(baseUrl) {
  const normalizedBaseUrl = base(baseUrl);
  const useLocalRie = envFlag('LAMBDA_LOCAL_RIE', looksLikeLocalLambda(normalizedBaseUrl));

  if (useLocalRie) {
    return `${normalizedBaseUrl}/2015-03-31/functions/function/invocations`;
  }

  return normalizedBaseUrl;
}

export function invokeProcessor(baseUrl, payload, options = {}) {
  return http.post(
    lambdaInvokeUrl(baseUrl),
    JSON.stringify(payload),
    jsonParams('process_order', options.tags),
  );
}

export function invokeReset(resetUrl, options = {}) {
  return http.post(resetUrl, null, requestParams('cold_reset', options.tags));
}