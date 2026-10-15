-- Copiado de /home/bernardo/Documentos/tcc/files/09-scripts.md (popular_orders_summary.sql, F2-S, 50.000 linhas).
INSERT INTO orders (
  id, customer_id, status, total_amount, discount_amount, final_amount,
  shipping_zip_code, shipping_street, shipping_number, shipping_complement,
  shipping_city, shipping_state, created_at, updated_at
)
SELECT
  gen_random_uuid(),
  ('00000000-0000-4000-8000-' || lpad((1 + (g % 5000))::text, 12, '0'))::uuid,
  (ARRAY['PENDING','CONFIRMED','PROCESSING','SHIPPED','DELIVERED','CANCELLED'])[1 + floor(random()*6)::int],
  total, disc, total - disc,
  lpad((floor(random()*99999999))::text, 8, '0'),
  'Rua Teste ' || g,
  (1 + (g % 9999))::text,
  CASE WHEN g % 3 = 0 THEN 'Apto ' || (g % 50) ELSE NULL END,
  (ARRAY['Lavras','Belo Horizonte','Sao Paulo','Campinas','Curitiba'])[1 + (g % 5)],
  (ARRAY['MG','MG','SP','SP','PR'])[1 + (g % 5)],
  now() - (random() * interval '12 hours'),
  now() - (random() * interval '12 hours')
FROM (
  SELECT g, total, round((total * pct)::numeric, 2) AS disc
  FROM (
    SELECT g, round((50 + random()*950)::numeric, 2) AS total, (random()*0.3) AS pct
    FROM generate_series(1, 50000) AS g
  ) base
) sub;
