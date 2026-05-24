from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = ROOT / "infrastructure" / "docker-compose.processor.yml"

SPRING_URL = "http://localhost:9001/2015-03-31/functions/function/invocations"
QUARKUS_JVM_URL = "http://localhost:9002/2015-03-31/functions/function/invocations"
QUARKUS_NATIVE_URL = "http://localhost:9003/2015-03-31/functions/function/invocations"

AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "local"
AWS_SECRET_ACCESS_KEY = "local"
PROCESSED_ORDERS_TABLE = "processed_orders"
STOCK_RESERVATIONS_TABLE = "stock_reservations"

LOCAL_IMAGES = (
	"public.ecr.aws/aws-dynamodb-local/aws-dynamodb-local:latest",
	"public.ecr.aws/aws-cli/aws-cli:2.25.12",
	"order-processor-springboot:lambda",
	"order-processor-quarkus:lambda-jvm",
	"order-processor-quarkus:lambda-native",
)

KEYBOARD_ID = "93b6c5c8-0f9a-4c2a-8c4c-6f0f3d6a9c2b"
MOUSE_ID = "7b5c3d6a-07be-4d47-8a3f-60c0c10b6510"
CUSTOMER_ID = "8b9d7b5e-9d2a-4b4f-8c5a-8b3d6f5d1a11"

NUMERIC_FIELDS = (
	"shippingCost",
	"taxAmount",
	"finalAmount",
)
COMPARABLE_FIELDS = (
	"fiscalNumber",
	"shippingCost",
	"taxAmount",
	"finalAmount",
	"estimatedDeliveryDays",
)


@dataclass(frozen=True)
class ProcessorVariant:
	name: str
	url: str


PROCESSOR_VARIANTS = (
	ProcessorVariant("Spring Boot JVM", SPRING_URL),
	ProcessorVariant("Quarkus JVM", QUARKUS_JVM_URL),
	ProcessorVariant("Quarkus Native", QUARKUS_NATIVE_URL),
)


@dataclass(frozen=True)
class PayloadCase:
	name: str
	payload: dict[str, Any]
	expected_reservations: int
	expected_validation_message: str | None = None

	@property
	def order_id(self) -> str:
		return self.payload["orderId"]

	@property
	def is_valid(self) -> bool:
		return self.expected_validation_message is None


@dataclass(frozen=True)
class InvocationOutcome:
	status_code: int
	body: dict[str, Any]
	reservation_count: int

	@property
	def is_error(self) -> bool:
		return "errorMessage" in self.body


def single_item_payload(order_id: str, state: str, city: str, zip_code: str) -> dict[str, Any]:
	return {
		"orderId": order_id,
		"customerId": CUSTOMER_ID,
		"items": [
			{
				"productId": KEYBOARD_ID,
				"productName": "Mechanical Keyboard",
				"quantity": 2,
				"unitPrice": 199.90,
			}
		],
		"shippingAddress": {
			"zipCode": zip_code,
			"state": state,
			"city": city,
		},
		"totalAmount": 399.80,
	}


PAYLOAD_CASES = (
	PayloadCase(
		name="payload MG",
		payload=single_item_payload("10000000-0000-4000-8000-000000000001", "MG", "Lavras", "37200-000"),
		expected_reservations=1,
	),
	PayloadCase(
		name="payload SP",
		payload=single_item_payload("20000000-0000-4000-8000-000000000002", "SP", "Sao Paulo", "01000-000"),
		expected_reservations=1,
	),
	PayloadCase(
		name="payload RS",
		payload=single_item_payload("30000000-0000-4000-8000-000000000003", "RS", "Porto Alegre", "90000-000"),
		expected_reservations=1,
	),
	PayloadCase(
		name="payload BA",
		payload=single_item_payload("40000000-0000-4000-8000-000000000004", "BA", "Salvador", "40000-000"),
		expected_reservations=1,
	),
	PayloadCase(
		name="payload AM",
		payload=single_item_payload("50000000-0000-4000-8000-000000000005", "AM", "Manaus", "69000-000"),
		expected_reservations=1,
	),
	PayloadCase(
		name="payload com multiplos itens",
		payload={
			"orderId": "60000000-0000-4000-8000-000000000006",
			"customerId": CUSTOMER_ID,
			"items": [
				{
					"productId": KEYBOARD_ID,
					"productName": "Mechanical Keyboard",
					"quantity": 2,
					"unitPrice": 199.90,
				},
				{
					"productId": MOUSE_ID,
					"productName": "Wireless Mouse",
					"quantity": 1,
					"unitPrice": 49.90,
				},
			],
			"shippingAddress": {
				"zipCode": "37200-000",
				"state": "MG",
				"city": "Lavras",
			},
			"totalAmount": 449.70,
		},
		expected_reservations=2,
	),
	PayloadCase(
		name="payload invalido sem items",
		payload={
			"orderId": "70000000-0000-4000-8000-000000000007",
			"customerId": CUSTOMER_ID,
			"items": [],
			"shippingAddress": {
				"zipCode": "37200-000",
				"state": "MG",
				"city": "Lavras",
			},
			"totalAmount": 399.80,
		},
		expected_reservations=0,
		expected_validation_message="items must contain at least one item",
	),
	PayloadCase(
		name="payload invalido com quantity = 0",
		payload={
			"orderId": "80000000-0000-4000-8000-000000000008",
			"customerId": CUSTOMER_ID,
			"items": [
				{
					"productId": KEYBOARD_ID,
					"productName": "Mechanical Keyboard",
					"quantity": 0,
					"unitPrice": 199.90,
				}
			],
			"shippingAddress": {
				"zipCode": "37200-000",
				"state": "MG",
				"city": "Lavras",
			},
			"totalAmount": 399.80,
		},
		expected_reservations=0,
		expected_validation_message="items[0].quantity must be at least 1",
	),
)


class OrderProcessorEquivalenceTest(unittest.TestCase):

	@classmethod
	def setUpClass(cls) -> None:
		cls._run([
			"docker", "compose", "-f", str(COMPOSE_FILE),
			"--profile", "quarkus", "--profile", "quarkus-native",
			"down", "-v",
		], check=False)
		build_images = os.getenv("ORDER_PROCESSOR_EQUIVALENCE_BUILD_IMAGES", "false").lower() == "true"
		if not build_images:
			cls.require_local_images()

		cls._run(["./gradlew", "clean", "build", "--no-daemon"], cwd=ROOT / "order-processor" / "springboot")
		cls._run(["./gradlew", "clean", "build", "--no-daemon"], cwd=ROOT / "order-processor" / "quarkus")
		if build_images:
			cls.build_jvm_images()

		cls._run([
			"./gradlew", "build",
			"-Dquarkus.package.type=native",
			"-Dquarkus.native.container-build=true",
			"-Dquarkus.native.native-image-xmx=6g",
			"--no-daemon",
		], cwd=ROOT / "order-processor" / "quarkus")
		if build_images:
			cls.build_native_image()

		compose_up = [
			"docker",
			"compose",
			"-f",
			str(COMPOSE_FILE),
			"--profile",
			"quarkus",
			"--profile",
			"quarkus-native",
			"up",
			"-d",
			"dynamodb-local",
			"dynamodb-init",
			"order-processor-springboot",
			"order-processor-quarkus",
			"order-processor-quarkus-native",
		]
		cls._run(compose_up)
		cls.addClassCleanup(
			cls._run,
			[
				"docker", "compose", "-f", str(COMPOSE_FILE),
				"--profile", "quarkus", "--profile", "quarkus-native",
				"down", "-v",
			],
			ROOT,
			False,
		)
		cls.dynamo_db = boto3.client(
			"dynamodb",
			endpoint_url="http://localhost:8000",
			region_name=AWS_REGION,
			aws_access_key_id=AWS_ACCESS_KEY_ID,
			aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
		)

	def test_fixed_payloads_produce_equivalent_outputs(self) -> None:
		for case in PAYLOAD_CASES:
			with self.subTest(case=case.name):
				outcomes = {
					variant.name: self.invoke_and_capture(variant, case)
					for variant in PROCESSOR_VARIANTS
				}
				if case.is_valid:
					self.assert_valid_equivalence(case, outcomes)
				else:
					self.assert_invalid_equivalence(case, outcomes)
				self.delete_order_data(case.order_id)

	def invoke_and_capture(self, variant: ProcessorVariant, case: PayloadCase) -> InvocationOutcome:
		self.delete_order_data(case.order_id)
		body = json.dumps(case.payload).encode("utf-8")
		last_error: Exception | None = None

		for _ in range(30):
			request = Request(
				variant.url,
				data=body,
				headers={"Content-Type": "application/json"},
				method="POST",
			)
			try:
				with urlopen(request, timeout=20) as response:
					payload = json.loads(response.read().decode("utf-8"), parse_float=Decimal)
					return InvocationOutcome(
						status_code=response.getcode(),
						body=payload,
						reservation_count=self.count_reservations(case.order_id),
					)
			except URLError as error:
				last_error = error
				time.sleep(1)

		raise AssertionError(f"Failed to invoke {variant.name} at {variant.url}: {last_error}")

	def assert_valid_equivalence(
		self,
		case: PayloadCase,
		outcomes: dict[str, InvocationOutcome],
	) -> None:
		baseline_name, baseline = next(iter(outcomes.items()))
		for variant_name, outcome in outcomes.items():
			self.assertFalse(outcome.is_error, f"{case.name}: {variant_name} returned error payload {outcome.body}")
			self.assertEqual(outcome.status_code, 200, f"{case.name}: unexpected {variant_name} HTTP status")

		for variant_name, outcome in outcomes.items():
			if variant_name == baseline_name:
				continue
			for field in COMPARABLE_FIELDS:
				if field in NUMERIC_FIELDS:
					self.assertEqual(
						self.to_decimal(baseline.body[field]),
						self.to_decimal(outcome.body[field]),
						f"{case.name}: field {field} differs between {baseline_name} and {variant_name}",
					)
				else:
					self.assertEqual(
						baseline.body[field],
						outcome.body[field],
						f"{case.name}: field {field} differs between {baseline_name} and {variant_name}",
					)
				self.assertEqual(
					baseline.reservation_count,
					outcome.reservation_count,
					f"{case.name}: reservation count differs between {baseline_name} and {variant_name}",
				)
		self.assertEqual(baseline.reservation_count, case.expected_reservations, f"{case.name}: unexpected reservation count")

	def assert_invalid_equivalence(
		self,
		case: PayloadCase,
		outcomes: dict[str, InvocationOutcome],
	) -> None:
		baseline_name, baseline = next(iter(outcomes.items()))
		for variant_name, outcome in outcomes.items():
			self.assertTrue(outcome.is_error, f"{case.name}: {variant_name} should return an error payload")
			self.assertIn(
				case.expected_validation_message,
				outcome.body["errorMessage"],
				f"{case.name}: {variant_name} message mismatch",
			)
			self.assertEqual(outcome.reservation_count, case.expected_reservations, f"{case.name}: reservations should not persist")
			self.assertEqual(
				baseline.reservation_count,
				outcome.reservation_count,
				f"{case.name}: reservation count differs between {baseline_name} and {variant_name}",
			)

	def count_reservations(self, order_id: str) -> int:
		response = self.dynamo_db.query(
			TableName=STOCK_RESERVATIONS_TABLE,
			KeyConditionExpression="orderId = :orderId",
			ExpressionAttributeValues={
				":orderId": {"S": order_id},
			},
		)
		return response["Count"]

	def delete_order_data(self, order_id: str) -> None:
		self.dynamo_db.delete_item(
			TableName=PROCESSED_ORDERS_TABLE,
			Key={"orderId": {"S": order_id}},
		)
		response = self.dynamo_db.query(
			TableName=STOCK_RESERVATIONS_TABLE,
			KeyConditionExpression="orderId = :orderId",
			ExpressionAttributeValues={
				":orderId": {"S": order_id},
			},
		)
		for item in response["Items"]:
			self.dynamo_db.delete_item(
				TableName=STOCK_RESERVATIONS_TABLE,
				Key={
					"orderId": {"S": order_id},
					"productId": item["productId"],
				},
			)

	@staticmethod
	def to_decimal(value: Decimal | float | int | str) -> Decimal:
		return value if isinstance(value, Decimal) else Decimal(str(value))

	@classmethod
	def require_local_images(cls) -> None:
		missing_images = [image for image in LOCAL_IMAGES if not cls.image_exists(image)]
		if missing_images:
			formatted = ", ".join(missing_images)
			raise unittest.SkipTest(
				"Missing local Docker image(s): "
				f"{formatted}. Build/pull them first or run with ORDER_PROCESSOR_EQUIVALENCE_BUILD_IMAGES=true."
			)

	@staticmethod
	def image_exists(image: str) -> bool:
		result = subprocess.run(
			["docker", "image", "inspect", image],
			cwd=ROOT,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			text=True,
		)
		return result.returncode == 0

	@classmethod
	def build_jvm_images(cls) -> None:
		cls._run(["docker", "build", "-t", "order-processor-springboot:lambda", "."], cwd=ROOT / "order-processor" / "springboot")
		cls._run([
			"docker", "build", "-f", "Dockerfile.jvm", "-t", "order-processor-quarkus:lambda-jvm", ".",
		], cwd=ROOT / "order-processor" / "quarkus")

	@classmethod
	def build_native_image(cls) -> None:
		cls._run([
			"docker", "build", "-f", "Dockerfile.native", "-t", "order-processor-quarkus:lambda-native", ".",
		], cwd=ROOT / "order-processor" / "quarkus")

	@staticmethod
	def _run(
		command: list[str],
		cwd: Path = ROOT,
		check: bool = True,
	) -> subprocess.CompletedProcess[str]:
		return subprocess.run(command, cwd=cwd, check=check, text=True)


if __name__ == "__main__":
	unittest.main(verbosity=2)