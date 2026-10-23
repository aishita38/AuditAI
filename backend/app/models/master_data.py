"""Rule-only master datasets. Business keys are independent of internal IDs."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey, JSON
from backend.app.db import Base


class VendorMaster(Base):
    __tablename__ = 'vendor_master'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(String(80), unique=True, nullable=False, index=True)
    vendor_name = Column(String(300), nullable=False)
    bank_account = Column(String(100))
    ifsc = Column(String(30))
    address = Column(Text)
    phone = Column(String(80))
    gstin = Column(String(40))
    pan = Column(String(30))
    director_names = Column(Text)
    onboarding_date = Column(Date, nullable=False)
    status = Column(String(40), nullable=False)


class EmployeeMaster(Base):
    __tablename__ = 'employee_master'
    id = Column(Integer, primary_key=True)
    employee_id = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    bank_account = Column(String(100))
    pan = Column(String(30))
    department = Column(String(150), nullable=False)
    join_date = Column(Date, nullable=False)
    exit_date = Column(Date)
    monthly_salary = Column(Numeric(15, 2), nullable=False)


class PayrollPayment(Base):
    __tablename__ = 'payroll_payments'
    id = Column(Integer, primary_key=True)
    payment_id = Column(String(80), unique=True, nullable=False, index=True)
    # Deliberately not an FK: unknown employees are valid screening inputs.
    employee_id = Column(String(80), nullable=False, index=True)
    employee_name = Column(String(300), nullable=False)
    bank_account = Column(String(100))
    amount = Column(Numeric(15, 2), nullable=False)
    pay_period = Column(String(7), nullable=False)
    payment_date = Column(Date, nullable=False)


class MasterImportHistory(Base):
    __tablename__ = 'master_import_history'
    id = Column(Integer, primary_key=True)
    dataset = Column(String(40), nullable=False, index=True)
    filename = Column(String(200), nullable=False)
    file_sha256 = Column(String(64), nullable=True)
    imported_by = Column(Integer, ForeignKey('auth_users.id'), nullable=False)
    imported_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    status = Column(String(30), nullable=False)
    inserted = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    rejected = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=False, default=list)
