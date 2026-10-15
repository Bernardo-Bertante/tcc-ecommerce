# Texto das consultas por operacao (normalizado pelo pg_stat_statements)


## create_order

- textos distintos: SB-noval 3, QJ 2; identicos nos dois: 0


**SB-noval** (chamadas somadas nas rodadas)

-   59467 x  `INSERT INTO order_items (id, order_id, product_id, product_name, quantity, unit_price, subtotal) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`
-   19822 x  `INSERT INTO orders (id, customer_id, status, total_amount, discount_amount, final_amount, shipping_zip_code, shipping_street, shipping_number, shipping_city, shipping_state, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) RETURNING id`
-    9912 x  `INSERT INTO orders (id, customer_id, status, total_amount, discount_amount, final_amount, shipping_zip_code, shipping_street, shipping_number, shipping_complement, shipping_city, shipping_state, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) RETURNING id`

**QJ** (chamadas somadas nas rodadas)

-   59464 x  `INSERT INTO order_items ( id, order_id, product_id, product_name, quantity, unit_price, subtotal ) VALUES ( $1, $2, $3, $4, $5, $6, $7 )`
-   29733 x  `INSERT INTO orders ( id, customer_id, status, total_amount, discount_amount, final_amount, shipping_zip_code, shipping_street, shipping_number, shipping_complement, shipping_city, shipping_state, created_at, updated_at ) VALUES ( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14 )`

## get_order

- textos distintos: SB-noval 2, QJ 2; identicos nos dois: 0


**SB-noval** (chamadas somadas nas rodadas)

-   58085 x  `SELECT orders.* FROM orders WHERE orders.id = $1 LIMIT $2`
-   58085 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id = $1`

**QJ** (chamadas somadas nas rodadas)

-   58085 x  `SELECT * FROM orders WHERE id = $1`
-   58085 x  `SELECT * FROM order_items WHERE order_id = $1`

## get_orders_by_customer

- textos distintos: SB-noval 10, QJ 3; identicos nos dois: 1


**SB-noval** (chamadas somadas nas rodadas)

-   13830 x  `SELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3`  [IDENTICO no outro]
-   13830 x  `SELECT COUNT(*) FROM orders WHERE customer_id = $1`
-    5264 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6, $7)`
-    3040 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4)`
-    2316 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6)`
-    1654 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5)`
-     718 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6, $7, $8)`
-     550 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6, $7, $8, $9)`
-     250 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`
-      38 x  `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, order_items.unit_price, order_items.subtotal FROM order_items WHERE order_items.order_id IN ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`

**QJ** (chamadas somadas nas rodadas)

-   13830 x  `SELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3`  [IDENTICO no outro]
-   13830 x  `SELECT * FROM order_items WHERE order_id = ANY($1)`
-   13830 x  `SELECT COUNT(*) AS total_orders FROM orders WHERE customer_id = $1`

## get_summary

- textos distintos: SB-noval 5, QJ 5; identicos nos dois: 5


**SB-noval** (chamadas somadas nas rodadas)

-    1842 x  `SELECT customer_id, COALESCE(SUM(final_amount), $4) AS total_spent, COUNT(*) AS order_count FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY customer_id ORDER BY total_spent DESC, order_count DESC LIMIT $3`  [IDENTICO no outro]
-    1842 x  `SELECT CAST(created_at AT TIME ZONE $3 AS DATE) AS revenue_day, COALESCE(SUM(final_amount), $4) AS revenue, COUNT(*) AS order_count FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY CAST(created_at AT TIME ZONE 'UTC' AS DATE) ORDER BY revenue_day ASC`  [IDENTICO no outro]
-    1842 x  `SELECT status, COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY status`  [IDENTICO no outro]
-    1842 x  `SELECT COALESCE(SUM(final_amount), $3) AS total_revenue FROM orders WHERE created_at >= $1 AND created_at < $2`  [IDENTICO no outro]
-    1842 x  `SELECT COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2`  [IDENTICO no outro]

**QJ** (chamadas somadas nas rodadas)

-    1842 x  `SELECT customer_id, COALESCE(SUM(final_amount), $4) AS total_spent, COUNT(*) AS order_count FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY customer_id ORDER BY total_spent DESC, order_count DESC LIMIT $3`  [IDENTICO no outro]
-    1842 x  `SELECT CAST(created_at AT TIME ZONE $3 AS DATE) AS revenue_day, COALESCE(SUM(final_amount), $4) AS revenue, COUNT(*) AS order_count FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY CAST(created_at AT TIME ZONE 'UTC' AS DATE) ORDER BY revenue_day ASC`  [IDENTICO no outro]
-    1842 x  `SELECT status, COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY status`  [IDENTICO no outro]
-    1842 x  `SELECT COALESCE(SUM(final_amount), $3) AS total_revenue FROM orders WHERE created_at >= $1 AND created_at < $2`  [IDENTICO no outro]
-    1842 x  `SELECT COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2`  [IDENTICO no outro]

## insert_status_history

- textos distintos: SB-noval 2, QJ 1; identicos nos dois: 0


**SB-noval** (chamadas somadas nas rodadas)

-   29734 x  `INSERT INTO order_status_history (id, order_id, new_status, changed_at) VALUES ($1, $2, $3, $4) RETURNING id`
-   11054 x  `INSERT INTO order_status_history (id, order_id, previous_status, new_status, changed_at) VALUES ($1, $2, $3, $4, $5) RETURNING id`

**QJ** (chamadas somadas nas rodadas)

-   40786 x  `INSERT INTO order_status_history ( id, order_id, previous_status, new_status, changed_at ) VALUES ( $1, $2, $3, $4, $5 )`

## nao_classificado

- textos distintos: SB-noval 2, QJ 2; identicos nos dois: 2


**SB-noval** (chamadas somadas nas rodadas)

-     410 x  `select extract($1 from clock_timestamp())::bigint, coalesce(state,$2), count(*) from pg_stat_activity where datname=$3 and backend_type=$4 and pid<>pg_backend_pid() group by 2`  [IDENTICO no outro]
-       4 x  `select extract($1 from clock_timestamp()), numbackends, xact_commit, xact_rollback, blks_read, blks_hit, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, session_time, active_time, idle_in_transaction_time, sessions, sessions_abandoned, sessions_fatal, sessions_killed from pg_stat_database where datname=$2`  [IDENTICO no outro]

**QJ** (chamadas somadas nas rodadas)

-     410 x  `select extract($1 from clock_timestamp())::bigint, coalesce(state,$2), count(*) from pg_stat_activity where datname=$3 and backend_type=$4 and pid<>pg_backend_pid() group by 2`  [IDENTICO no outro]
-       4 x  `select extract($1 from clock_timestamp()), numbackends, xact_commit, xact_rollback, blks_read, blks_hit, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, session_time, active_time, idle_in_transaction_time, sessions, sessions_abandoned, sessions_fatal, sessions_killed from pg_stat_database where datname=$2`  [IDENTICO no outro]

## update_status

- textos distintos: SB-noval 1, QJ 1; identicos nos dois: 0


**SB-noval** (chamadas somadas nas rodadas)

-   11054 x  `UPDATE orders SET customer_id = $1, status = $2, total_amount = $3, discount_amount = $4, final_amount = $5, shipping_zip_code = $6, shipping_street = $7, shipping_number = $8, shipping_complement = $9, shipping_city = $10, shipping_state = $11, created_at = $12, updated_at = $13 WHERE orders.id = $14`

**QJ** (chamadas somadas nas rodadas)

-   11053 x  `UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3`
