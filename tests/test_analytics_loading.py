from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.app.db import Base
from backend.app.models.expense import ExpenseClaim, Case
from backend.app.api.analytics import (
    get_benford_law_distribution, screen_related_parties, screen_sod_violations,
)


def test_screening_results_use_bounded_queries_without_receipt_payloads():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert get_benford_law_distribution(db) == []
        for i in range(20):
            claim = ExpenseClaim(claim_id=f'T{i}', employee_id=f'E{i}',
                employee_name='Sharma', vendor_name='Sharma Consulting' if i == 0 else 'Travel Ltd',
                claimed_amount=100, claimed_date=date(2025, 1, 1))
            db.add(claim)
            db.add(Case(claim=claim, maker_id=f'E{i}'))
        db.commit()
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn, cursor, statement, *args: statements.append(statement))
    with Session(engine) as db:
        distribution = get_benford_law_distribution(db)
        assert distribution[0]['actual'] == 100
        assert len(statements) == 1
        assert 'JOIN' not in statements[0].upper()
        statements.clear()
        related = screen_related_parties(db)
        assert [row['claim_id'] for row in related] == ['T0']
        assert len(statements) == 1
        assert all('receipts' not in sql and 'ocr_results' not in sql for sql in statements)
        statements.clear()
        assert len(screen_sod_violations(db)) == 20
        assert len(statements) == 2
    engine.dispose()
