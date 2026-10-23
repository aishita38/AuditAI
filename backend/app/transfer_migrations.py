"""Add the claim link without rebuilding or deleting the transfer ledger."""
from sqlalchemy import inspect, text
from backend.app.models.transfer import BankTransfer


def migrate_transfer_claim_link(engine):
    with engine.begin() as connection:
        columns = {c['name'] for c in inspect(connection).get_columns('bank_transfers')}
        if 'claim_id' not in columns:
            connection.execute(text('ALTER TABLE bank_transfers ADD COLUMN claim_id VARCHAR(50) REFERENCES expense_claims(claim_id)'))
        for index in BankTransfer.__table__.indexes:
            index.create(connection, checkfirst=True)
