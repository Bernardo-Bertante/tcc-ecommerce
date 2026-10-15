-- Executado ao fim de cada rodada, com a app parada, DEPOIS do dump de pg_stat_statements.
-- \set d = diretorio de saida. Exploratorio.
create extension if not exists pageinspect;
-- \o :d/layout_orders.csv
\copy (select ctid::text as ctid, (ctid::text::point)[0]::int as blk, (ctid::text::point)[1]::int as off, id, customer_id, status, created_at, updated_at, xmin::text::bigint as xmin from orders order by created_at, id) to '/home/ec2-user/res/out/r4-springboot-noval/layout_orders.csv' with csv header
-- \o :d/layout_order_items.csv
\copy (select ctid::text as ctid, (ctid::text::point)[0]::int as blk, id, order_id from order_items) to '/home/ec2-user/res/out/r4-springboot-noval/layout_order_items.csv' with csv header
-- \o :d/paginas_orders.csv
\copy (select p.blkno, count(*) filter (where i.lp_flags=1) as normal, count(*) filter (where i.lp_flags=3) as dead, count(*) filter (where i.lp_flags=2) as redirect, count(*) filter (where i.lp_flags=0) as unused, count(*) filter (where i.lp_flags=1 and i.t_xmax<>0) as versao_antiga, min(i.t_xmin::text::bigint) as xmin_min, max(i.t_xmin::text::bigint) as xmin_max from generate_series(0, pg_relation_size('orders')/8192-1) p(blkno), lateral heap_page_items(get_raw_page('orders', p.blkno::int)) i group by p.blkno order by p.blkno) to '/home/ec2-user/res/out/r4-springboot-noval/paginas_orders.csv' with csv header
-- \o
-- visibilidade e estado das tabelas
\o /home/ec2-user/res/out/r4-springboot-noval/estado_visibilidade.tsv
select 'orders' t, relpages, reltuples, relallvisible from pg_class where relname='orders';
select 'pg_stat_user_tables' t, relname, n_live_tup, n_dead_tup, n_tup_ins, n_tup_upd, n_tup_hot_upd, n_tup_newpage_upd, autovacuum_count, autoanalyze_count, last_autovacuum, last_autoanalyze from pg_stat_user_tables where schemaname='public';
\o
-- EXPLAIN direto, 3 execucoes de cada consulta do get_summary (mesma sessao, sem cache frio garantido)
\o /home/ec2-user/res/out/r4-springboot-noval/explain_direto_antes.txt
\set w 'created_at >= timestamptz ''2026-01-01'' and created_at < timestamptz ''2027-01-01'''
\qecho ##### status
explain (analyze, buffers, verbose, format text) select status, count(*) as total_orders from orders where :w group by status;
explain (analyze, buffers, format text) select status, count(*) as total_orders from orders where :w group by status;
explain (analyze, buffers, format text) select status, count(*) as total_orders from orders where :w group by status;
\qecho ##### count
explain (analyze, buffers, format text) select count(*) as total_orders from orders where :w;
explain (analyze, buffers, format text) select count(*) as total_orders from orders where :w;
\qecho ##### sum
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) as total_revenue from orders where :w;
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) as total_revenue from orders where :w;
\qecho ##### top_customers
explain (analyze, buffers, format text) select customer_id, coalesce(sum(final_amount),0) as total_spent, count(*) as order_count from orders where :w group by customer_id order by total_spent desc, order_count desc limit 10;
explain (analyze, buffers, format text) select customer_id, coalesce(sum(final_amount),0) as total_spent, count(*) as order_count from orders where :w group by customer_id order by total_spent desc, order_count desc limit 10;
\qecho ##### revenue_by_day
explain (analyze, buffers, format text) select cast(created_at at time zone 'UTC' as date) as revenue_day, coalesce(sum(final_amount),0) as revenue, count(*) as order_count from orders where :w group by cast(created_at at time zone 'UTC' as date) order by revenue_day asc;
explain (analyze, buffers, format text) select cast(created_at at time zone 'UTC' as date) as revenue_day, coalesce(sum(final_amount),0) as revenue, count(*) as order_count from orders where :w group by cast(created_at at time zone 'UTC' as date) order by revenue_day asc;
\qecho ##### forcado_index_scan (mesmo plano de get_summary: heap na ordem do indice)
set enable_seqscan=off; set enable_bitmapscan=off; set enable_indexonlyscan=off;
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) from orders where :w;
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) from orders where :w;
reset enable_seqscan; reset enable_bitmapscan; reset enable_indexonlyscan;
\o
-- teste de causalidade: reordena o heap pela ordem de created_at e repete o Index Scan forcado
CLUSTER orders USING idx_orders_created_at;
ANALYZE orders;
\o /home/ec2-user/res/out/r4-springboot-noval/explain_direto_depois_cluster.txt
\qecho ##### forcado_index_scan_apos_CLUSTER
set enable_seqscan=off; set enable_bitmapscan=off; set enable_indexonlyscan=off;
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) from orders where :w;
explain (analyze, buffers, format text) select coalesce(sum(final_amount),0) from orders where :w;
reset enable_seqscan; reset enable_bitmapscan; reset enable_indexonlyscan;
\qecho ##### plano_padrao_apos_CLUSTER
explain (analyze, buffers, format text) select status, count(*) as total_orders from orders where :w group by status;
explain (analyze, buffers, format text) select customer_id, coalesce(sum(final_amount),0) as total_spent, count(*) as order_count from orders where :w group by customer_id order by total_spent desc, order_count desc limit 10;
\o
