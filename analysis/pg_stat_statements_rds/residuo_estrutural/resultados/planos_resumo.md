# Planos por operacao e texto de consulta (assinatura = tipos de no + relacao/indice)


## create_order: `INSERT INTO order_items ( id, order_id, product_id, product_name, quantity, unit_price, subtotal ) VALUES ( $1, $2, $3, `
- SB-noval: 0 amostras
- QJ: 1184 amostras
    - 1184 x ModifyTable[order_items] > Result

## create_order: `INSERT INTO order_items (id, order_id, product_id, product_name, quantity, unit_price, subtotal) VALUES ($1, $2, $3, $4,`
- SB-noval: 1176 amostras
    - 1176 x ModifyTable[order_items] > Result
- QJ: 0 amostras

## create_order: `INSERT INTO orders ( id, customer_id, status, total_amount, discount_amount, final_amount, shipping_zip_code, shipping_s`
- SB-noval: 0 amostras
- QJ: 640 amostras
    -  640 x ModifyTable[orders] > Result

## create_order: `INSERT INTO orders (id, customer_id, status, total_amount, discount_amount, final_amount, shipping_zip_code, shipping_st`
- SB-noval: 635 amostras
    -  635 x ModifyTable[orders] > Result
- QJ: 0 amostras

## get_order: `SELECT * FROM order_items WHERE order_id = $1`
- SB-noval: 0 amostras
- QJ: 1158 amostras
    - 1154 x Bitmap Heap Scan[order_items] > Bitmap Index Scan
    -    4 x Seq Scan[order_items]

## get_order: `SELECT * FROM orders WHERE id = $1`
- SB-noval: 0 amostras
- QJ: 1141 amostras
    - 1123 x Index Scan[orders/orders_pkey]
    -   18 x Seq Scan[orders]

## get_order: `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, ord`
- SB-noval: 1140 amostras
    - 1135 x Bitmap Heap Scan[order_items] > Bitmap Index Scan
    -    5 x Seq Scan[order_items]
- QJ: 0 amostras

## get_order: `SELECT orders.* FROM orders WHERE orders.id = $1 LIMIT 2`
- SB-noval: 1147 amostras
    - 1140 x Limit > Index Scan[orders/orders_pkey]
    -    7 x Limit > Seq Scan[orders]
- QJ: 0 amostras

## get_orders_by_customer: `SELECT * FROM order_items WHERE order_id = ANY($1)`
- SB-noval: 0 amostras
- QJ: 289 amostras
    -  284 x Bitmap Heap Scan[order_items] > Bitmap Index Scan
    -    5 x Seq Scan[order_items]

## get_orders_by_customer: `SELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3`
- SB-noval: 256 amostras
    -  217 x Limit > Sort > Bitmap Heap Scan[orders] > Bitmap Index Scan
    -   37 x Limit > Sort > Index Scan[orders/idx_orders_customer_id]
    -    2 x Limit > Sort > Seq Scan[orders]
- QJ: 269 amostras
    -  224 x Limit > Sort > Bitmap Heap Scan[orders] > Bitmap Index Scan
    -   40 x Limit > Sort > Index Scan[orders/idx_orders_customer_id]
    -    5 x Limit > Sort > Seq Scan[orders]

## get_orders_by_customer: `SELECT COUNT(*) AS total_orders FROM orders WHERE customer_id = $1`
- SB-noval: 0 amostras
- QJ: 278 amostras
    -  273 x Aggregate > Index Only Scan[orders/idx_orders_customer_id]
    -    5 x Aggregate > Seq Scan[orders]

## get_orders_by_customer: `SELECT COUNT(*) FROM orders WHERE customer_id = $1`
- SB-noval: 289 amostras
    -  283 x Aggregate > Index Only Scan[orders/idx_orders_customer_id]
    -    4 x Aggregate > Bitmap Heap Scan[orders] > Bitmap Index Scan
    -    2 x Aggregate > Seq Scan[orders]
- QJ: 0 amostras

## get_orders_by_customer: `SELECT order_items.id, order_items.order_id, order_items.product_id, order_items.product_name, order_items.quantity, ord`
- SB-noval: 264 amostras
    -  258 x Bitmap Heap Scan[order_items] > Bitmap Index Scan
    -    6 x Seq Scan[order_items]
- QJ: 0 amostras

## get_summary: `SELECT CAST(created_at AT TIME ZONE 'UTC' AS DATE) AS revenue_day, COALESCE(SUM(final_amount), 0) AS revenue, COUNT(*) A`
- SB-noval: 37 amostras
    -   33 x Aggregate > Sort > Index Scan[orders/idx_orders_created_at]
    -    4 x Aggregate > Sort > Seq Scan[orders]
- QJ: 30 amostras
    -   29 x Aggregate > Sort > Index Scan[orders/idx_orders_created_at]
    -    1 x Aggregate > Sort > Seq Scan[orders]

## get_summary: `SELECT COALESCE(SUM(final_amount), 0) AS total_revenue FROM orders WHERE created_at >= $1 AND created_at < $2`
- SB-noval: 43 amostras
    -   38 x Aggregate > Index Scan[orders/idx_orders_created_at]
    -    5 x Aggregate > Seq Scan[orders]
- QJ: 35 amostras
    -   33 x Aggregate > Index Scan[orders/idx_orders_created_at]
    -    2 x Aggregate > Seq Scan[orders]

## get_summary: `SELECT COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2`
- SB-noval: 22 amostras
    -   15 x Aggregate > Index Only Scan[orders/idx_orders_created_at]
    -    7 x Aggregate > Seq Scan[orders]
- QJ: 42 amostras
    -   39 x Aggregate > Index Only Scan[orders/idx_orders_created_at]
    -    3 x Aggregate > Seq Scan[orders]

## get_summary: `SELECT customer_id, COALESCE(SUM(final_amount), 0) AS total_spent, COUNT(*) AS order_count FROM orders WHERE created_at `
- SB-noval: 49 amostras
    -   44 x Limit > Sort > Aggregate > Index Scan[orders/idx_orders_created_at]
    -    3 x Limit > Sort > Aggregate > Seq Scan[orders]
    -    2 x Limit > Sort > Aggregate > Sort > Index Scan[orders/idx_orders_created_at]
- QJ: 29 amostras
    -   24 x Limit > Sort > Aggregate > Index Scan[orders/idx_orders_created_at]
    -    4 x Limit > Sort > Aggregate > Sort > Index Scan[orders/idx_orders_created_at]
    -    1 x Limit > Sort > Aggregate > Seq Scan[orders]

## get_summary: `SELECT status, COUNT(*) AS total_orders FROM orders WHERE created_at >= $1 AND created_at < $2 GROUP BY status`
- SB-noval: 49 amostras
    -   42 x Aggregate > Index Scan[orders/idx_orders_created_at]
    -    7 x Aggregate > Seq Scan[orders]
- QJ: 23 amostras
    -   19 x Aggregate > Index Scan[orders/idx_orders_created_at]
    -    2 x Aggregate > Sort > Index Scan[orders/idx_orders_created_at]
    -    2 x Aggregate > Seq Scan[orders]

## insert_status_history: `INSERT INTO order_status_history ( id, order_id, previous_status, new_status, changed_at ) VALUES ( $1, $2, $3, $4, $5 )`
- SB-noval: 0 amostras
- QJ: 816 amostras
    -  816 x ModifyTable[order_status_history] > Result

## insert_status_history: `INSERT INTO order_status_history (id, order_id, new_status, changed_at) VALUES ($1, $2, $3, $4) RETURNING id`
- SB-noval: 596 amostras
    -  596 x ModifyTable[order_status_history] > Result
- QJ: 0 amostras

## insert_status_history: `INSERT INTO order_status_history (id, order_id, previous_status, new_status, changed_at) VALUES ($1, $2, $3, $4, $5) RET`
- SB-noval: 240 amostras
    -  240 x ModifyTable[order_status_history] > Result
- QJ: 0 amostras

## nao_classificado: `SELECT 1 FROM ONLY "public"."orders" x WHERE "id" OPERATOR(pg_catalog.=) $1 FOR KEY SHARE OF x`
- SB-noval: 2012 amostras
    - 1972 x LockRows > Index Scan[orders/orders_pkey]
    -   40 x LockRows > Seq Scan[orders]
- QJ: 2000 amostras
    - 1960 x LockRows > Index Scan[orders/orders_pkey]
    -   40 x LockRows > Seq Scan[orders]

## nao_classificado: `select extract(epoch from clock_timestamp())::bigint, coalesce(state,'null'), count(*) from pg_stat_activity where datna`
- SB-noval: 4 amostras
    -    4 x Aggregate > Sort > Nested Loop > Function Scan > Seq Scan[pg_database]
- QJ: 13 amostras
    -   13 x Aggregate > Sort > Nested Loop > Function Scan > Seq Scan[pg_database]

## update_status: `UPDATE orders SET customer_id = $1, status = $2, total_amount = $3, discount_amount = $4, final_amount = $5, shipping_zi`
- SB-noval: 217 amostras
    -  216 x ModifyTable[orders] > Index Scan[orders/orders_pkey]
    -    1 x ModifyTable[orders] > Seq Scan[orders]
- QJ: 0 amostras

## update_status: `UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3`
- SB-noval: 0 amostras
- QJ: 214 amostras
    -  212 x ModifyTable[orders] > Index Scan[orders/orders_pkey]
    -    2 x ModifyTable[orders] > Seq Scan[orders]


# Nos de scan: estimativa x real e blocos por linha (mediana por amostra; nos com >= 200 linhas reais)

op                       cond      no                         n lin_real_med est/real_med blk/linha_med heapfetch/lin
get_summary              QJ        Index Only Scan/orders    39         5688         0.00         0.122         0.293
get_summary              QJ        Index Scan/orders        111         6808         0.00         0.462           nan
get_summary              QJ        Seq Scan/orders            8         6744         1.01         0.020           nan
get_summary              SB-noval  Index Only Scan/orders    15         7672         0.00         0.032         0.283
get_summary              SB-noval  Index Scan/orders        159         8664         0.00         0.099           nan
get_summary              SB-noval  Seq Scan/orders           25         1367         1.00         0.021           nan


# No raiz: blocos e duracao por amostra, por operacao (mediana)

op                       cond          n blocos_med dur_ms_med
create_order             QJ         1824        5.0      0.142
create_order             SB-noval   1811        5.0      0.184
get_order                QJ         2299        3.0      0.025
get_order                SB-noval   2287        3.0      0.027
get_orders_by_customer   QJ          836        7.0      0.046
get_orders_by_customer   SB-noval    809        7.0      0.052
get_summary              QJ          159     1869.0      7.779
get_summary              SB-noval    200      893.5     12.681
insert_status_history    QJ          816        5.0      0.206
insert_status_history    SB-noval    836        5.0      0.210
nao_classificado         QJ         2013        4.0      0.014
nao_classificado         SB-noval   2016        4.0      0.014
update_status            QJ          214       15.0      0.114
update_status            SB-noval    217       15.0      0.117
