"""Finding-level precision/recall against independently authored synthetic truth."""
import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.master_import_service import normalize_row
from backend.app.features.master_rules import evaluate_vendors,evaluate_payroll,configuration
DATA=ROOT/'data/master_rule_demo'


def signature(f):
    return json.dumps({k:sorted(v) for k,v in f['involved_record_ids'].items()},sort_keys=True)


def evaluate():
    def read(dataset):
        with (DATA/(dataset+'.csv')).open(encoding='utf-8') as file:return [normalize_row(dataset,r) for r in csv.DictReader(file)]
    with (DATA/'vendor-linked-transactions-fixture.csv').open(encoding='utf-8') as file:transactions=list(csv.DictReader(file))
    expected=json.loads((DATA/'ground-truth.json').read_text(encoding='utf-8'))
    findings=evaluate_vendors(read('vendor-master'),configuration(),transactions)+evaluate_payroll(read('employee-roster'),read('payroll-payments'))
    result=[]
    for rule in expected['decoys']:
        truth={signature(f) for f in expected['findings'] if f['rule_id']==rule}
        predicted={signature(f) for f in findings if f['rule_id']==rule}
        tp=len(truth&predicted);fp=len(predicted-truth);fn=len(truth-predicted)
        result.append(dict(rule_id=rule,tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else 0,recall=tp/(tp+fn) if tp+fn else 0,scope='Fixture-only vendor-linked transactions' if rule=='VENDOR_NEW_LARGE_PAYMENT' else 'Imported-schema synthetic records'))
    return result


if __name__=='__main__':
    result=evaluate()
    print('Rule | TP | FP | FN | Precision | Recall')
    for r in result:print(f"{r['rule_id']} | {r['tp']} | {r['fp']} | {r['fn']} | {r['precision']:.2%} | {r['recall']:.2%}")
    print('Synthetic fixtures only. New-vendor payment integration is unavailable in the live app. Expense ML scores and claim metrics are unchanged.')
    out=ROOT/'scripts/artifacts/master-rule-evaluation.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
