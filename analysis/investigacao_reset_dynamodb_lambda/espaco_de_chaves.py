#!/usr/bin/env python3
"""Reproduz o espaco de chaves que o k6 escreve no DynamoDB nos cenarios L1/L2/L3.

Replica benchmark/lib/data-generator.js (createPrng/uuidFromPrng/uuidAt/
makeProcessingRequestPayload) e benchmark/lib/workload.js:132
(makeProcessingRequestPayload(iteration + 20000)) para contar quantas chaves
DISTINTAS de `processed_orders` (HASH orderId) e `stock_reservations`
(HASH orderId + RANGE productId) uma rodada produz. Como o repositorio so faz
PutItem (sobrescreve a chave), esse numero e o teto de itens da tabela.

Uso: python3 espaco_de_chaves.py
"""

SEED = 20260512
POOL = 4096
MASK = 0xFFFFFFFF


def prng(seed):
    state = seed & MASK
    while True:
        # createPrng do data-generator.js (LCG de 32 bits)
        state = (state * 1664525 + 1013904223) & MASK
        yield state / 4294967296.0


def build_pool(size=POOL, seed=SEED):
    gen = prng(seed)
    pool = []
    for _ in range(size):
        parts = [int(next(gen) * 4294967296) & MASK for _ in range(6)]
        pool.append('%08x-%04x-%04x-%04x-%08x%04x' % (
            parts[0], parts[1] & 0xFFFF, (parts[2] & 0x0FFF) | 0x4000,
            (parts[3] & 0x3FFF) | 0x8000, parts[4], parts[5] & 0xFFFF))
    return pool


def keys_for_round(n_iterations, pool):
    """Chaves escritas por uma rodada de n_iterations invocacoes."""
    orders, reservations = set(), set()
    for iteration in range(n_iterations):
        index = iteration + 20000                      # workload.js:132
        order_id = pool[(3000 + index) % len(pool)]    # data-generator.js:157
        orders.add(order_id)
        item_count = 1 + (index % 3)                   # data-generator.js:145
        for item_index in range(item_count):
            j = index * 10 + item_index
            product_id = pool[(1000 + j) % len(pool)]  # data-generator.js:131
            reservations.add((order_id, product_id))
    return orders, reservations


def main():
    pool = build_pool()
    print(f'pool de UUIDs: seed={SEED} tamanho={len(pool)} (distintos: {len(set(pool))})')
    # n de uma rodada real de L2 (l2-springboot-r1-summary.json: http_reqs=20354)
    for n in (4096, 10000, 20354, 27759, 100000):
        orders, reservations = keys_for_round(n, pool)
        print(f'  n={n:6d} invocacoes -> processed_orders: {len(orders):5d} chaves '
              f'distintas | stock_reservations: {len(reservations):6d} chaves distintas')
    print()
    print('ItemCount real das tabelas na conta (describe-table, 22/09/2026):')
    print('  processed_orders   = 4101   (teto simulado: %d)' % len(keys_for_round(100000, pool)[0]))
    print('  stock_reservations = 12293  (teto simulado: %d)' % len(keys_for_round(100000, pool)[1]))


if __name__ == '__main__':
    main()
