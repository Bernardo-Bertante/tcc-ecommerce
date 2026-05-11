-- =====================================================================
-- V1__create_order_tables.sql
-- Schema inicial do Order Service (TCC UFLA).
--
-- Fonte única de verdade do schema, compartilhada entre as três variantes:
--   - order-service/springboot       (Spring Boot + WebFlux + R2DBC)
--   - order-service/quarkus (JVM)    (Quarkus + Hibernate Reactive Panache)
--   - order-service/quarkus (Native) (mesmo projeto Quarkus, GraalVM)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Tabela: orders
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    id                  UUID            PRIMARY KEY,
    customer_id         UUID            NOT NULL,
    status              VARCHAR(20)     NOT NULL,
    total_amount        NUMERIC(12,2)   NOT NULL,
    discount_amount     NUMERIC(12,2)   NOT NULL DEFAULT 0,
    final_amount        NUMERIC(12,2)   NOT NULL,
    shipping_zip_code   VARCHAR(9)      NOT NULL,
    shipping_street     VARCHAR(255)    NOT NULL,
    shipping_number     VARCHAR(10)     NOT NULL,
    shipping_complement VARCHAR(100),
    shipping_city       VARCHAR(100)    NOT NULL,
    shipping_state      CHAR(2)         NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT chk_orders_status CHECK (
        status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED')
    ),
    CONSTRAINT chk_orders_total_amount_non_negative    CHECK (total_amount    >= 0),
    CONSTRAINT chk_orders_discount_amount_non_negative CHECK (discount_amount >= 0),
    CONSTRAINT chk_orders_final_amount_non_negative    CHECK (final_amount    >= 0),
    CONSTRAINT chk_orders_discount_le_total            CHECK (discount_amount <= total_amount),
    CONSTRAINT chk_orders_final_eq_total_minus_discount
        CHECK (final_amount = total_amount - discount_amount)
);

-- ---------------------------------------------------------------------
-- Tabela: order_items
-- ---------------------------------------------------------------------
CREATE TABLE order_items (
    id           UUID           PRIMARY KEY,
    order_id     UUID           NOT NULL,
    product_id   UUID           NOT NULL,
    product_name VARCHAR(255)   NOT NULL,
    quantity     INTEGER        NOT NULL,
    unit_price   NUMERIC(12,2)  NOT NULL,
    subtotal     NUMERIC(12,2)  NOT NULL,
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT chk_order_items_quantity_positive   CHECK (quantity   >= 1),
    CONSTRAINT chk_order_items_unit_price_positive CHECK (unit_price  > 0),
    CONSTRAINT chk_order_items_subtotal_non_negative CHECK (subtotal >= 0)
);

-- ---------------------------------------------------------------------
-- Tabela: order_status_history
-- ---------------------------------------------------------------------
CREATE TABLE order_status_history (
    id              UUID         PRIMARY KEY,
    order_id        UUID         NOT NULL,
    previous_status VARCHAR(20),
    new_status      VARCHAR(20)  NOT NULL,
    changed_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT fk_status_history_order
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT chk_status_history_new_status CHECK (
        new_status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED')
    ),
    CONSTRAINT chk_status_history_previous_status CHECK (
        previous_status IS NULL OR previous_status IN
            ('PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED')
    )
);

-- ---------------------------------------------------------------------
-- Índices
-- ---------------------------------------------------------------------
CREATE INDEX idx_orders_customer_id            ON orders(customer_id);
CREATE INDEX idx_orders_status                 ON orders(status);
CREATE INDEX idx_orders_created_at             ON orders(created_at);
CREATE INDEX idx_order_items_order_id          ON order_items(order_id);
CREATE INDEX idx_order_status_history_order_id ON order_status_history(order_id);
