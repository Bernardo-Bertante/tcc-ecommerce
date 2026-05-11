#!/usr/bin/env bash
set -euo pipefail

base_url="${ORDER_SERVICE_URL:-http://localhost:8081}"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

wait_for_health() {
  local output_file="$1"
  local attempts=60
  local delay_seconds=2
  local temp_file="$work_dir/health-attempt.json"
  local last_error=""

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "$base_url/q/health" > "$temp_file"; then
      if [[ "$(json_get "$temp_file" "status")" == "UP" ]]; then
        mv "$temp_file" "$output_file"
        return 0
      fi

      last_error="Health endpoint responded without status UP on attempt $attempt"
    else
      last_error="curl failed while waiting for health on attempt $attempt"
    fi

    sleep "$delay_seconds"
  done

  echo "$last_error" >&2
  return 1
}

json_get() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)

for part in sys.argv[2].split("."):
    value = value[part]

print(value)
PY
}

assert_json_equals() {
  local file_path="$1"
  local key_path="$2"
  local expected="$3"
  local actual
  actual="$(json_get "$file_path" "$key_path")"

  if [[ "$actual" != "$expected" ]]; then
    echo "Expected $key_path to be $expected but got $actual" >&2
    return 1
  fi
}

assert_json_number_at_least() {
  local file_path="$1"
  local key_path="$2"
  local minimum="$3"

  python3 - "$file_path" "$key_path" "$minimum" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)

for part in sys.argv[2].split("."):
    value = value[part]

if float(value) < float(sys.argv[3]):
    raise SystemExit(f"Expected {sys.argv[2]} to be >= {sys.argv[3]} but got {value}")
PY
}

health_file="$work_dir/health.json"
wait_for_health "$health_file"
assert_json_equals "$health_file" "status" "UP"

customer_id="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
product_id="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"

payload_file="$work_dir/create-order.json"
cat > "$payload_file" <<JSON
{
  "customerId": "$customer_id",
  "discountAmount": 1.00,
  "items": [
    {
      "productId": "$product_id",
      "productName": "Native Smoke Keyboard",
      "quantity": 2,
      "unitPrice": 9.99
    }
  ],
  "shippingAddress": {
    "zipCode": "37200-000",
    "street": "Main Street",
    "number": "123",
    "complement": null,
    "city": "Lavras",
    "state": "MG"
  }
}
JSON

created_file="$work_dir/created-order.json"
curl --fail --silent --show-error \
  --header "Content-Type: application/json" \
  --data "@$payload_file" \
  "$base_url/orders" > "$created_file"

assert_json_equals "$created_file" "customerId" "$customer_id"
assert_json_equals "$created_file" "status" "PENDING"
assert_json_equals "$created_file" "finalAmount" "18.98"

order_id="$(json_get "$created_file" "id")"
fetched_file="$work_dir/fetched-order.json"
curl --fail --silent --show-error "$base_url/orders/$order_id" > "$fetched_file"
assert_json_equals "$fetched_file" "id" "$order_id"
assert_json_equals "$fetched_file" "status" "PENDING"

from_date="$(python3 - <<'PY'
from datetime import date, timedelta
print(date.today() - timedelta(days=1))
PY
)"
to_date="$(python3 - <<'PY'
from datetime import date, timedelta
print(date.today() + timedelta(days=1))
PY
)"

summary_file="$work_dir/summary.json"
curl --fail --silent --show-error \
  "$base_url/orders/summary?fromDate=$from_date&toDate=$to_date" > "$summary_file"
assert_json_number_at_least "$summary_file" "totalOrders" 1
assert_json_number_at_least "$summary_file" "totalRevenue" 18.98
assert_json_number_at_least "$summary_file" "ordersByStatus.PENDING" 1

echo "Native container smoke passed for order $order_id"