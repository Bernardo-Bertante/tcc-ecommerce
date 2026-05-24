#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
DYNAMODB_ENDPOINT="${DYNAMODB_ENDPOINT:-http://dynamodb-local:8000}"
PROCESSED_ORDERS_TABLE="${PROCESSED_ORDERS_TABLE:-processed_orders}"
STOCK_RESERVATIONS_TABLE="${STOCK_RESERVATIONS_TABLE:-stock_reservations}"

aws_dynamodb() {
  aws --endpoint-url "$DYNAMODB_ENDPOINT" --region "$AWS_REGION" dynamodb "$@"
}

wait_for_dynamodb() {
  attempts=0
  until aws_dynamodb list-tables >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "DynamoDB Local did not become available at $DYNAMODB_ENDPOINT" >&2
      exit 1
    fi
    sleep 1
  done
}

create_processed_orders_table() {
  if aws_dynamodb describe-table --table-name "$PROCESSED_ORDERS_TABLE" >/dev/null 2>&1; then
    echo "Table $PROCESSED_ORDERS_TABLE already exists"
    return
  fi

  aws_dynamodb create-table \
    --table-name "$PROCESSED_ORDERS_TABLE" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions AttributeName=orderId,AttributeType=S \
    --key-schema AttributeName=orderId,KeyType=HASH >/dev/null

  aws_dynamodb wait table-exists --table-name "$PROCESSED_ORDERS_TABLE"
  echo "Created table $PROCESSED_ORDERS_TABLE"
}

create_stock_reservations_table() {
  if aws_dynamodb describe-table --table-name "$STOCK_RESERVATIONS_TABLE" >/dev/null 2>&1; then
    echo "Table $STOCK_RESERVATIONS_TABLE already exists"
    return
  fi

  aws_dynamodb create-table \
    --table-name "$STOCK_RESERVATIONS_TABLE" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions AttributeName=orderId,AttributeType=S AttributeName=productId,AttributeType=S \
    --key-schema AttributeName=orderId,KeyType=HASH AttributeName=productId,KeyType=RANGE >/dev/null

  aws_dynamodb wait table-exists --table-name "$STOCK_RESERVATIONS_TABLE"
  echo "Created table $STOCK_RESERVATIONS_TABLE"
}

wait_for_dynamodb
create_processed_orders_table
create_stock_reservations_table
aws_dynamodb list-tables
