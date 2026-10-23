"""Small synthetic benchmark, including a legitimate refund cycle as a hard negative."""
import csv
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.api.transfers import parse_transfer
from backend.app.features.transfer_cycles import find_cycles


def evaluate():
    with (ROOT/'frontend/public/sample-transfers.csv').open() as f:
        rows=[parse_transfer(r) for r in csv.DictReader(f)]
    scenarios=[('planted_three_account_cycle',True,rows[:3]),('planted_two_account_cycle',True,rows[3:5]),
               ('normal_open_chain',False,rows[5:7]),('different_currencies',False,rows[7:9]),
               ('simultaneous_entries',False,rows[9:11]),('outside_window',False,rows[11:13])]
    refund=[parse_transfer(dict(transaction_id=f'REFUND-{i}',sender_account=a,receiver_account=b,amount='500.00',currency='INR',timestamp=t)) for i,a,b,t in [(1,'TEST-CUSTOMER','TEST-MERCHANT','2026-03-01T10:00:00Z'),(2,'TEST-MERCHANT','TEST-CUSTOMER','2026-03-02T10:00:00Z')]]
    scenarios.append(('legitimate_purchase_and_refund',False,refund))
    items=[]; counts=dict(true_positive=0,false_positive=0,true_negative=0,false_negative=0)
    for name,positive,transfers in scenarios:
        detected=bool(find_cycles(transfers)['cycles'])
        key=('true_positive' if detected else 'false_negative') if positive else ('false_positive' if detected else 'true_negative')
        counts[key]+=1
        items.append(dict(scenario=name,expected_review_concern=positive,detected=detected,result=key))
    tp,fp,tn,fn=(counts[k] for k in ['true_positive','false_positive','true_negative','false_negative'])
    return dict(dataset='Seven hand-authored synthetic scenarios; not a production benchmark',
                unit='scenario',settings=dict(window_days=7,max_hops=4),**counts,
                precision=tp/(tp+fp),recall=tp/(tp+fn),false_positive_rate=fp/(fp+tn),
                scenarios=items,limitations='A legitimate refund is structurally a cycle and is flagged. Labels describe fictional context. Results do not measure real-world fraud detection or ML performance.')


if __name__=='__main__':
    report=evaluate()
    path=ROOT/'scripts/artifacts/circular-payment-evaluation.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
