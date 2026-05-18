export const FARGATE_THRESHOLDS = {
  'http_req_failed{phase:load}': [{ threshold: 'rate<0.005', abortOnFail: true }],
  'http_req_duration{phase:load}': ['p(95)<2000', 'p(99)<5000'],
};

export const LAMBDA_THRESHOLDS = {
  'http_req_failed{phase:load}': [{ threshold: 'rate<0.01', abortOnFail: true }],
  'http_req_duration{phase:load}': ['p(95)<5000', 'p(99)<10000'],
};

export const SMOKE_THRESHOLDS = {
  'http_req_failed{phase:load}': ['rate<0.05'],
  'http_req_duration{phase:load}': ['p(95)<10000'],
};
