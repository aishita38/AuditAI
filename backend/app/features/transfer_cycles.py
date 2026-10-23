"""Bounded, chronological same-currency cycle screening; no ML inference."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal


def find_cycles(rows, window_days=7, max_hops=4, max_results=100, budget=200000):
    edges = sorted(rows, key=lambda r: (r['timestamp'], r['transaction_id']))
    outgoing = defaultdict(list)
    for e in edges:
        outgoing[(e['sender_account'], e['currency'])].append(e)
    results = []
    examined = 0
    limited = False

    def visit(path, accounts):
        nonlocal examined, limited
        first, last = path[0], path[-1]
        for edge in outgoing[(last['receiver_account'], first['currency'])]:
            examined += 1
            if examined > budget or len(results) >= max_results:
                limited = True
                return
            # Strict time ordering: tied timestamps do not prove a flow sequence.
            if edge['timestamp'] <= last['timestamp']:
                continue
            if edge['timestamp'] - first['timestamp'] > timedelta(days=window_days):
                break
            closed = edge['receiver_account'] == first['sender_account']
            if not closed and edge['receiver_account'] in accounts:
                continue
            new_path = path + [edge]
            if closed:
                amounts = [Decimal(str(e['amount'])) for e in new_path]
                results.append(dict(
                    transaction_ids=[e['transaction_id'] for e in new_path],
                    accounts=accounts + [edge['receiver_account']],
                    currency=first['currency'],
                    initial_amount=str(amounts[0]), returned_amount=str(amounts[-1]),
                    return_ratio=float(amounts[-1] / amounts[0]),
                    bottleneck_amount=str(min(amounts)),
                    elapsed_hours=round((edge['timestamp']-first['timestamp']).total_seconds()/3600, 2),
                    reason='Chronologically ordered transfers return to the starting account within the review window. Account links do not prove the same funds were recycled.',
                    transfers=[dict(e, amount=str(e['amount']), timestamp=e['timestamp'].isoformat()+'Z') for e in new_path],
                ))
            elif len(new_path) < max_hops:
                visit(new_path, accounts + [edge['receiver_account']])
            if limited:
                return

    for edge in edges:
        if limited:
            break
        if edge['sender_account'] != edge['receiver_account']:
            visit([edge], [edge['sender_account'], edge['receiver_account']])
    return dict(cycles=results, search_limited=limited, examined_edges=examined,
                window_days=window_days, max_hops=max_hops, max_results=max_results,
                transfer_count=len(edges), excluded_self_transfers=sum(e['sender_account']==e['receiver_account'] for e in edges),
                interpretation='Potential circular payment pattern — review required, not proof of fraud.')
