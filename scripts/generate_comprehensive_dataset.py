"""
AuditAI — Comprehensive Unified Anomaly Dataset Generator
==========================================================
Generates a single uploadable CSV containing ALL anomaly types from the three
original datasets (25 risk categories + 15 ERP fraud types + 5 expense fraud
types), consolidated into 35 distinct patterns.

Company: Prism Industries Ltd (fictional Indian conglomerate)
Output:  data/comprehensive_audit_claims.csv  (~5000 records)
"""
import csv
import math
import os
import random
from datetime import date, timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
from faker import Faker

random.seed(2024)
np.random.seed(2024)
fake = Faker("en_IN")
fake.seed_instance(2024)

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "comprehensive_audit_claims.csv"

# ============================================================================
# COMPANY STRUCTURE: Prism Industries Ltd
# ============================================================================

COMPANY = "Prism Industries Ltd"

DEPARTMENTS = {
    "FIN": "Finance & Accounts",
    "HR": "Human Resources",
    "IT": "Information Technology",
    "PROC": "Procurement & Supply Chain",
    "OPS": "Operations & Manufacturing",
    "SALES": "Sales & Business Development",
    "MKT": "Marketing & Communications",
    "LEGAL": "Legal & Compliance",
    "ADMIN": "Administration & Facilities",
    "R&D": "Research & Development",
}

# Realistic Indian employee roster with designations and approval limits
EMPLOYEES = [
    # C-Suite
    {"id": "EMP001", "name": "Rajesh Krishnamurthy", "dept": "OPS", "role": "CEO", "limit": 100_000_000},
    {"id": "EMP002", "name": "Anita Deshmukh", "dept": "FIN", "role": "CFO", "limit": 50_000_000},
    {"id": "EMP003", "name": "Vikram Malhotra", "dept": "IT", "role": "CTO", "limit": 25_000_000},
    # VPs
    {"id": "EMP004", "name": "Sanjay Verma", "dept": "PROC", "role": "VP", "limit": 5_000_000},
    {"id": "EMP005", "name": "Priya Nambiar", "dept": "SALES", "role": "VP", "limit": 5_000_000},
    {"id": "EMP006", "name": "Deepak Joshi", "dept": "FIN", "role": "VP", "limit": 5_000_000},
    {"id": "EMP007", "name": "Kavitha Raghavan", "dept": "HR", "role": "VP", "limit": 5_000_000},
    {"id": "EMP008", "name": "Arjun Bhatia", "dept": "OPS", "role": "VP", "limit": 5_000_000},
    # Directors
    {"id": "EMP009", "name": "Neha Gupta", "dept": "MKT", "role": "Director", "limit": 1_000_000},
    {"id": "EMP010", "name": "Rahul Sharma", "dept": "PROC", "role": "Director", "limit": 1_000_000},
    {"id": "EMP011", "name": "Sneha Iyer", "dept": "FIN", "role": "Director", "limit": 1_000_000},
    {"id": "EMP012", "name": "Amit Patel", "dept": "IT", "role": "Director", "limit": 1_000_000},
    {"id": "EMP013", "name": "Lakshmi Sundaram", "dept": "LEGAL", "role": "Director", "limit": 1_000_000},
    {"id": "EMP014", "name": "Karthik Menon", "dept": "R&D", "role": "Director", "limit": 1_000_000},
    # Senior Managers
    {"id": "EMP015", "name": "Pooja Reddy", "dept": "FIN", "role": "Sr. Manager", "limit": 250_000},
    {"id": "EMP016", "name": "Suresh Nair", "dept": "PROC", "role": "Sr. Manager", "limit": 250_000},
    {"id": "EMP017", "name": "Divya Pillai", "dept": "HR", "role": "Sr. Manager", "limit": 250_000},
    {"id": "EMP018", "name": "Rohan Kulkarni", "dept": "IT", "role": "Sr. Manager", "limit": 250_000},
    {"id": "EMP019", "name": "Meera Chatterjee", "dept": "SALES", "role": "Sr. Manager", "limit": 250_000},
    {"id": "EMP020", "name": "Arun Saxena", "dept": "OPS", "role": "Sr. Manager", "limit": 250_000},
    # Managers
    {"id": "EMP021", "name": "Nisha Agarwal", "dept": "FIN", "role": "Manager", "limit": 50_000},
    {"id": "EMP022", "name": "Varun Kapoor", "dept": "PROC", "role": "Manager", "limit": 50_000},
    {"id": "EMP023", "name": "Shreya Banerjee", "dept": "MKT", "role": "Manager", "limit": 50_000},
    {"id": "EMP024", "name": "Akash Tiwari", "dept": "SALES", "role": "Manager", "limit": 50_000},
    {"id": "EMP025", "name": "Ritu Choudhary", "dept": "HR", "role": "Manager", "limit": 50_000},
    {"id": "EMP026", "name": "Gaurav Singh", "dept": "IT", "role": "Manager", "limit": 50_000},
    {"id": "EMP027", "name": "Ananya Bhatt", "dept": "OPS", "role": "Manager", "limit": 50_000},
    {"id": "EMP028", "name": "Manish Dubey", "dept": "ADMIN", "role": "Manager", "limit": 50_000},
    # Associates / Analysts
    {"id": "EMP029", "name": "Swati Mishra", "dept": "FIN", "role": "Analyst", "limit": 0},
    {"id": "EMP030", "name": "Nikhil Rao", "dept": "PROC", "role": "Analyst", "limit": 0},
    {"id": "EMP031", "name": "Tanvi Hegde", "dept": "IT", "role": "Analyst", "limit": 0},
    {"id": "EMP032", "name": "Siddharth Mukherjee", "dept": "SALES", "role": "Analyst", "limit": 0},
    {"id": "EMP033", "name": "Pallavi Deshpande", "dept": "HR", "role": "Analyst", "limit": 0},
    {"id": "EMP034", "name": "Rohit Pandey", "dept": "MKT", "role": "Analyst", "limit": 0},
    {"id": "EMP035", "name": "Aditi Kamath", "dept": "OPS", "role": "Analyst", "limit": 0},
    {"id": "EMP036", "name": "Harsh Vardhan", "dept": "R&D", "role": "Analyst", "limit": 0},
    {"id": "EMP037", "name": "Megha Srinivasan", "dept": "LEGAL", "role": "Analyst", "limit": 0},
    {"id": "EMP038", "name": "Kunal Bajaj", "dept": "ADMIN", "role": "Analyst", "limit": 0},
    # Ghost employee IDs (for payroll fraud)
    {"id": "EMP-GHOST-801", "name": "Ravi Kumar Phantom", "dept": "OPS", "role": "Associate", "limit": 0},
    {"id": "EMP-GHOST-802", "name": "Sunita Devi Ghost", "dept": "ADMIN", "role": "Associate", "limit": 0},
]
EMP_MAP = {e["id"]: e for e in EMPLOYEES}

# ============================================================================
# VENDOR MASTER
# ============================================================================

VERIFIED_VENDORS = [
    "Tata Consultancy Services", "Infosys Technologies Ltd", "Wipro Limited",
    "Reliance Industries Ltd", "Larsen & Toubro Ltd", "Bharti Airtel Ltd",
    "Blue Dart Express Ltd", "Delhivery Logistics", "DTDC Express Ltd",
    "HCL Technologies Ltd", "Tech Mahindra Ltd", "Godrej & Boyce Mfg",
    "Asian Paints Ltd", "Hindustan Unilever Ltd", "ITC Limited",
    "Mahindra & Mahindra Ltd", "Bosch India Ltd", "Siemens India Ltd",
    "ABB India Ltd", "Schneider Electric India", "Amazon Web Services India",
    "Google Cloud India", "Microsoft India Pvt Ltd", "SAP India Pvt Ltd",
    "Oracle India Pvt Ltd", "Deloitte India LLP", "EY India LLP",
    "KPMG India LLP", "PwC India LLP", "Grant Thornton India LLP",
    "Zomato Ltd", "Swiggy Pvt Ltd", "MakeMyTrip Ltd", "OYO Rooms",
    "IndiGo Airlines", "Air India Ltd", "Vistara Airlines",
    "Taj Hotels Resorts", "ITC Hotels", "The Oberoi Group",
    "Starbucks India", "Cafe Coffee Day", "Domino's Pizza India",
    "HP India Sales Pvt Ltd", "Dell Technologies India",
    "Croma (Infiniti Retail)", "Reliance Digital", "Flipkart India",
    "Urban Company", "BigBasket (Supermarket Grocery)",
]

FAKE_VENDORS = [
    # Typosquatted
    ("Tata Consultnacy Services", "Typosquatted clone of TCS"),
    ("Infosyss Technologies Pvt", "Typosquatted clone of Infosys"),
    ("Wiporo Limited", "Typosquatted clone of Wipro"),
    ("Relianse Industries", "Typosquatted clone of Reliance"),
    ("Larson & Turbo Ltd", "Typosquatted clone of L&T"),
    ("Starbuks India Coffee", "Typosquatted clone of Starbucks"),
    ("Zomto Food Services", "Typosquatted clone of Zomato"),
    ("Swiggi Delivery Pvt", "Typosquatted clone of Swiggy"),
    ("Flipkrt Online Services", "Typosquatted clone of Flipkart"),
    ("Amazn Web Services", "Typosquatted clone of AWS"),
    # Completely fake
    ("Sundry Repairs & Maintenance Co", "Non-existent vendor, generic name"),
    ("Quick Fix Solutions Pvt Ltd", "Unregistered entity"),
    ("Metro Office Supplies", "Cannot be verified"),
    ("Global Facility Services", "Generic shell name"),
    ("Prime Consulting Associates", "No GST registration found"),
]

SHELL_COMPANY_CLUSTER = [
    # Cluster 1: shared address + phone
    {"name": "Krishna Trading Co", "gstin": "07AAACK6188A1Z5", "phone": "+91-9876500001",
     "address": "Unit 4, Andheri Industrial Estate, Mumbai-400059"},
    {"name": "K Trading Solutions Pvt Ltd", "gstin": "07AAACK6188A2Z6", "phone": "+91-9876500001",
     "address": "Unit 4, Andheri Industrial Estate, Mumbai-400059"},
    {"name": "KTS Enterprises", "gstin": "07AAACK6188A3Z7", "phone": "+91-9876500002",
     "address": "Unit 4, Andheri Industrial Estate, Mumbai-400059"},
    # Cluster 2: shared bank account
    {"name": "Apex Consulting Services", "gstin": "27AAACA1234B1Z1", "bank": "50200098765432"},
    {"name": "Global Advisory Group LLP", "gstin": "27AAACG5678C1Z2", "bank": "50200098765432"},
    {"name": "Vertex Solutions Ltd", "gstin": "27AAACV9012D1Z3", "bank": "50200098765432"},
]

RELATED_PARTY_VENDORS = [
    {"name": "Verma Consulting Services", "linked_emp": "EMP004", "reason": "Surname match with VP Sanjay Verma"},
    {"name": "Malhotra Advisory LLP", "linked_emp": "EMP003", "reason": "Surname match with CTO Vikram Malhotra"},
    {"name": "Joshi & Associates", "linked_emp": "EMP006", "reason": "Surname match with VP Deepak Joshi"},
]

OFFSHORE_ENTITIES = [
    "Global Offshore Holdings BVI", "Cayman Structured Finance Ltd",
    "Mauritius Investment Vehicle Corp", "Singapore Shelf Co Pte Ltd",
]

CATEGORIES = [
    "Travel & Entertainment", "Office Supplies", "Consulting & Professional Fees",
    "IT Hardware & Software", "Marketing & Advertising", "Facilities & Utilities",
    "Raw Materials", "Logistics & Freight", "Salaries & Payroll",
    "Financial Instruments", "Revenue & Sales", "Rent & Leases",
    "Repairs & Maintenance", "Training & Development", "Miscellaneous",
]

# ============================================================================
# HELPERS
# ============================================================================

DATE_START = date(2024, 4, 1)  # FY 2024-25 start
DATE_END = date(2026, 3, 31)   # FY 2025-26 end
WEEKDAYS = [0, 1, 2, 3, 4]     # Mon-Fri

claim_counter = 0

def next_claim_id():
    global claim_counter
    claim_counter += 1
    return f"CLM-{claim_counter:05d}"

def random_weekday_date():
    while True:
        d = fake.date_between(start_date=DATE_START, end_date=DATE_END)
        if d.weekday() in WEEKDAYS:
            return d

def random_date():
    return fake.date_between(start_date=DATE_START, end_date=DATE_END)

def random_employee(exclude=None):
    pool = [e for e in EMPLOYEES if not e["id"].startswith("EMP-GHOST") and (exclude is None or e["id"] != exclude)]
    return random.choice(pool)

def round_amount(val):
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def make_row(claim_id, emp, amount, vendor, claimed_date, category, description,
             is_fraud, fraud_type, ocr_amount=None, ocr_vendor=None, ocr_confidence=None):
    return {
        "claim_id": claim_id,
        "employee_id": emp["id"],
        "employee_name": emp["name"],
        "claimed_amount": round_amount(amount),
        "vendor_name": vendor,
        "claimed_date": str(claimed_date),
        "category": category,
        "description": description,
        "is_fraud": is_fraud,
        "fraud_type": fraud_type,
        "ocr_amount": round_amount(ocr_amount) if ocr_amount is not None else "",
        "ocr_vendor": ocr_vendor or "",
        "ocr_confidence": round(ocr_confidence, 2) if ocr_confidence is not None else "",
    }

# ============================================================================
# NORMAL TRANSACTIONS (~3500)
# ============================================================================

print("Generating normal transactions...")
rows = []

for _ in range(3500):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS)
    cat = random.choice(CATEGORIES[:8])  # common categories
    amount = round(random.lognormvariate(math.log(5000), 1.2), 2)
    amount = min(amount, 500000)  # cap normal transactions
    d = random_weekday_date()
    desc_templates = [
        f"Invoice payment to {vendor} for {cat.lower()} services",
        f"PO-{random.randint(10000,99999)}: {cat} procurement from {vendor}",
        f"Monthly {cat.lower()} billing - {vendor}",
        f"Approved expense claim for {cat.lower()}",
        f"Vendor payment against invoice INV-{random.randint(1000,9999)}",
    ]
    # ~15% of normal transactions have receipt OCR
    ocr_amt = None
    ocr_vendor = None
    ocr_conf = None
    if random.random() < 0.15:
        ocr_amt = amount * random.uniform(0.98, 1.02)  # minor rounding
        ocr_vendor = vendor
        ocr_conf = random.uniform(0.85, 0.99)

    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d, cat,
        random.choice(desc_templates), False, "none",
        ocr_amt, ocr_vendor, ocr_conf
    ))

# ============================================================================
# ANOMALY INJECTION
# All 35 consolidated types, ~40 records each = ~1400 anomalous records
# ============================================================================

COUNT_PER_TYPE = 40
print(f"Injecting anomalies ({COUNT_PER_TYPE} per type)...")

# ---- 1. VENDOR OR INVOICE FRAUD / FAKE VENDORS ----
print("  1. Vendor or invoice fraud (fake/typosquatted vendors)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    fv, reason = random.choice(FAKE_VENDORS)
    amount = round(random.uniform(15000, 350000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, fv, d,
        random.choice(["Consulting & Professional Fees", "Office Supplies", "IT Hardware & Software"]),
        f"Vendor fraud: Payment to unverified entity '{fv}'. {reason}. GSTIN: 99INVALID{random.randint(1000,9999)}Z0",
        True, "Vendor or invoice fraud"
    ))

# ---- 2. PAYROLL FRAUD RISK ----
print("  2. Payroll fraud risk (ghost employees)")
for i in range(COUNT_PER_TYPE):
    ghost = random.choice([e for e in EMPLOYEES if "GHOST" in e["id"]])
    amount = round(random.uniform(500000, 2000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), ghost, amount, "Prism Industries Payroll", d,
        "Salaries & Payroll",
        f"Manual payroll adjustment of INR {amount:,.2f} to unverified employee {ghost['id']} outside batch run",
        True, "Payroll fraud risk"
    ))

# ---- 3. COMPLEX STRUCTURE RISK ----
print("  3. Complex structure risk (offshore entities)")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("VP", "Director")])
    entity = random.choice(OFFSHORE_ENTITIES)
    amount = round(random.uniform(2000000, 15000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, entity, d,
        "Financial Instruments",
        f"Intercompany sub-allocation license fee to offshore entity {entity}. Complex layered structure.",
        True, "Complex structure risk"
    ))

# ---- 4. MANUAL JOURNAL-ENTRY MANIPULATION ----
print("  4. Manual journal-entry manipulation")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("Sr. Manager", "Manager")])
    amount = round(random.uniform(1000000, 5000000), 2)
    d = random_weekday_date()
    vendor = random.choice(VERIFIED_VENDORS[:10])
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d,
        "Miscellaneous",
        f"Manual journal entry adjustment of INR {amount:,.2f}. No supporting PO, invoice, or vendor voucher attached. Posted directly to GL.",
        True, "Manual journal-entry manipulation"
    ))

# ---- 5. EXPENSE RECEIPT MISMATCH / AMOUNT INFLATION ----
print("  5. Expense receipt mismatch (OCR vs claimed)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS[30:])  # restaurants, hotels, etc.
    actual_amount = round(random.uniform(500, 8000), 2)
    inflated = round(actual_amount * random.uniform(2.5, 8.0), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, inflated, vendor, d,
        "Travel & Entertainment",
        f"Expense claim inflated: Claimed INR {inflated:,.2f}, receipt shows INR {actual_amount:,.2f}",
        True, "Expense receipt mismatch",
        ocr_amount=actual_amount, ocr_vendor=vendor, ocr_confidence=random.uniform(0.80, 0.95)
    ))

# ---- 6. ML-BASED UNKNOWN / EMERGING RISK ----
print("  6. ML-based unknown/emerging risk")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS)
    # Anomalous combination: unusual amount + unusual category for the vendor
    amount = round(random.uniform(800000, 5000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d,
        random.choice(["Financial Instruments", "Miscellaneous", "R&D Experimental"]),
        f"Autoencoder+IF ensemble flagged: Anomalous latent cluster. Unusual disbursement pattern to {vendor}.",
        True, "ML-based unknown or emerging risk"
    ))

# ---- 7. REVENUE MANIPULATION / CUT-OFF RISK ----
print("  7. Revenue manipulation / cut-off risk")
fy_end_dates = [date(2025, 3, 31), date(2026, 3, 31)]
quarter_ends = [date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31),
                date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
cutoff_dates = fy_end_dates + quarter_ends
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("VP", "Director", "Sr. Manager")])
    amount = round(random.uniform(2000000, 20000000), 2)
    d = random.choice(cutoff_dates)
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[:5]), d,
        "Revenue & Sales",
        f"Revenue posted on exact period-end date ({d}). INR {amount:,.2f} requires cut-off audit.",
        True, "Revenue manipulation / cut-off risk"
    ))

# ---- 8. DUPLICATE PAYMENT ----
print("  8. Duplicate payment / duplicate entry")
for i in range(COUNT_PER_TYPE // 2):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS)
    amount = round(random.uniform(20000, 200000), 2)
    d = random_weekday_date()
    d2 = d + timedelta(days=random.randint(0, 1))
    inv = f"INV-{vendor[:3].upper()}-{random.randint(10000,99999)}"
    for j, dt in enumerate([d, d2]):
        rows.append(make_row(
            next_claim_id(), emp, amount, vendor, dt,
            random.choice(CATEGORIES[:4]),
            f"{'Original' if j==0 else 'DUPLICATE'} payment of INR {amount:,.2f} to {vendor}. Invoice: {inv}",
            True, "Duplicate payment / duplicate entry"
        ))

# ---- 9. COMPLEX FINANCIAL-INSTRUMENT RISK ----
print("  9. Complex financial-instrument risk")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("CFO", "VP", "Director")])
    amount = round(random.uniform(5000000, 50000000), 2)
    d = random_weekday_date()
    instrument = random.choice(["currency derivative swap", "OTC interest rate hedge",
                                "cross-border FX forward", "credit default swap",
                                "structured note settlement"])
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(["ICICI Bank Treasury", "HDFC Securities", "JP Morgan India", "Citi India"]), d,
        "Financial Instruments",
        f"Complex instrument: {instrument} settlement of INR {amount:,.2f}. Requires specialized treasury audit.",
        True, "Complex financial-instrument risk"
    ))

# ---- 10. GHOST VENDOR RISK ----
print("  10. Ghost vendor risk (first-time vendor, large payment)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    ghost_vendor = f"Apex Ghost Enterprise {random.randint(100,999)}"
    amount = round(random.uniform(500000, 3000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, ghost_vendor, d,
        random.choice(CATEGORIES[:4]),
        f"First-time vendor '{ghost_vendor}' receiving INR {amount:,.2f} with zero prior transaction history.",
        True, "Ghost vendor risk"
    ))

# ---- 11. RELATED-PARTY RISK ----
print("  11. Related-party risk")
for i in range(COUNT_PER_TYPE):
    rp = random.choice(RELATED_PARTY_VENDORS)
    emp = EMP_MAP[rp["linked_emp"]]
    amount = round(random.uniform(100000, 2000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, rp["name"], d,
        "Consulting & Professional Fees",
        f"Related-party conflict: {rp['name']} — {rp['reason']}. INR {amount:,.2f}.",
        True, "Related-party risk"
    ))

# ---- 12. CIRCULAR PAYMENT PATTERNS ----
print("  12. Circular payment patterns")
# Ring: EMP015 requests, EMP016 approves -> Vendor linked to EMP015
#        EMP016 requests, EMP018 approves -> Vendor linked to EMP016
#        EMP018 requests, EMP015 approves -> Vendor linked to EMP018
CIRCULAR_RING = [
    {"requestor": "EMP015", "approver": "EMP016", "vendor": "Reddy Professional Services",
     "link": "Vendor shares mobile number +91-9900112233 with EMP015 (Pooja Reddy)"},
    {"requestor": "EMP016", "approver": "EMP018", "vendor": "Nair Tech Consulting LLP",
     "link": "Vendor shares bank A/C 40100012345678 with EMP016 (Suresh Nair)"},
    {"requestor": "EMP018", "approver": "EMP015", "vendor": "Kulkarni Associates",
     "link": "Vendor shares registered address with EMP018 (Rohan Kulkarni)"},
]
for i in range(COUNT_PER_TYPE):
    edge = CIRCULAR_RING[i % 3]
    emp = EMP_MAP[edge["requestor"]]
    amount = round(random.uniform(140000, 240000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, edge["vendor"], d,
        "Consulting & Professional Fees",
        f"Circular collusion: {emp['name']} requested, {EMP_MAP[edge['approver']]['name']} approved. {edge['link']}",
        True, "Circular payment patterns"
    ))

# ---- 13. SHELL COMPANY NETWORKS ----
print("  13. Shell company networks")
for i in range(COUNT_PER_TYPE):
    shell = random.choice(SHELL_COMPANY_CLUSTER)
    emp = random_employee()
    amount = round(random.uniform(200000, 1500000), 2)
    d = random_weekday_date()
    shared = f"Shared address: {shell.get('address', 'N/A')}" if "address" in shell else f"Shared bank: {shell.get('bank', 'N/A')}"
    rows.append(make_row(
        next_claim_id(), emp, amount, shell["name"], d,
        "Raw Materials",
        f"Shell network: {shell['name']} (GSTIN: {shell['gstin']}). {shared}. Regular large payments detected.",
        True, "Shell company networks"
    ))

# ---- 14. APPROVAL LIMIT VIOLATIONS ----
print("  14. Approval limit violations")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("Sr. Manager", "Manager")])
    # Amount exceeds their limit
    if emp["role"] == "Manager":
        amount = round(random.uniform(55000, 300000), 2)
        violation = f"Manager limit is INR 50,000 but approved INR {amount:,.2f}"
    else:
        amount = round(random.uniform(260000, 1200000), 2)
        violation = f"Sr. Manager limit is INR 250,000 but approved INR {amount:,.2f}"
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS), d,
        random.choice(CATEGORIES[:6]),
        f"Delegation of authority breach: {emp['name']} ({emp['role']}). {violation}.",
        True, "Approval limit violations"
    ))

# ---- 15. SPLIT INVOICE / THRESHOLD DODGING ----
print("  15. Split invoice / threshold dodging")
for i in range(COUNT_PER_TYPE // 4):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS)
    total = round(random.uniform(180000, 350000), 2)
    d = random_weekday_date()
    splits = random.randint(4, 7)
    per_split = round(total / splits, 2)
    for s in range(splits):
        actual = per_split + round(random.uniform(-500, 500), 2)
        actual = min(actual, 49500)  # keep below 50K threshold
        rows.append(make_row(
            next_claim_id(), emp, actual, vendor, d,
            random.choice(CATEGORIES[:4]),
            f"Split {s+1}/{splits}: INR {actual:,.2f} structured below INR 50,000 approval limit. Total: INR {total:,.2f}.",
            True, "Split invoice / threshold dodging"
        ))

# ---- 16. NEW VENDOR LARGE PAYMENT ----
print("  16. New vendor large payment")
for i in range(COUNT_PER_TYPE):
    new_vendor = f"NewCo {fake.company_suffix()} {random.randint(100,999)}"
    emp = random_employee()
    amount = round(random.uniform(1500000, 5000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, new_vendor, d,
        random.choice(CATEGORIES[:6]),
        f"High-risk: INR {amount:,.2f} to new vendor '{new_vendor}' within 7 days of onboarding.",
        True, "New vendor large payment"
    ))

# ---- 17. RELATED VENDORS SHARING BANK ACCOUNT ----
print("  17. Related vendors sharing bank account")
for i in range(COUNT_PER_TYPE):
    vendor = random.choice(SHELL_COMPANY_CLUSTER[3:])  # the bank-sharing cluster
    emp = random_employee()
    amount = round(random.uniform(100000, 800000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor["name"], d,
        "Consulting & Professional Fees",
        f"Procurement diversion: {vendor['name']} routes funds to shared bank A/C {vendor.get('bank', 'XXXXX')}.",
        True, "Related vendors sharing bank account"
    ))

# ---- 18. VENDOR PAYMENT VELOCITY SPIKES ----
print("  18. Vendor payment velocity spikes")
for i in range(COUNT_PER_TYPE // 10):
    vendor = random.choice(VERIFIED_VENDORS[:15])
    base_date = random_weekday_date()
    for j in range(10):
        emp = random_employee()
        amount = round(random.uniform(30000, 150000), 2)
        d = base_date + timedelta(hours=random.randint(0, 48))
        rows.append(make_row(
            next_claim_id(), emp, amount, vendor, base_date,
            random.choice(CATEGORIES[:4]),
            f"Velocity spike: Transaction {j+1}/10 to {vendor} within 48 hours. Possible invoice stuffing.",
            True, "Vendor payment velocity spikes"
        ))

# ---- 19. RELATED VENDORS SHARING ADDRESS ----
print("  19. Related vendors sharing address")
for i in range(COUNT_PER_TYPE):
    vendor = random.choice(SHELL_COMPANY_CLUSTER[:3])
    emp = random_employee()
    amount = round(random.uniform(80000, 500000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor["name"], d,
        "Logistics & Freight",
        f"Collusion risk: {vendor['name']} shares address '{vendor.get('address', 'N/A')}' with other bidding entities.",
        True, "Related vendors sharing address"
    ))

# ---- 20. RELATED VENDORS SHARING PHONE NUMBER ----
print("  20. Related vendors sharing phone number")
for i in range(COUNT_PER_TYPE):
    vendor = random.choice(SHELL_COMPANY_CLUSTER[:3])
    emp = random_employee()
    amount = round(random.uniform(50000, 400000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor["name"], d,
        "Raw Materials",
        f"Related vendor: {vendor['name']} shares phone {vendor.get('phone', 'N/A')} with competing entities.",
        True, "Related vendors sharing phone number"
    ))

# ---- 21. UNUSUAL AMOUNT ----
print("  21. Unusual amount (statistical outlier)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS)
    amount = round(random.uniform(1000000, 10000000), 2)
    d = random_weekday_date()
    cat = "Office Supplies"  # huge amount for this category = outlier
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d, cat,
        f"Statistical outlier: INR {amount:,.2f} is 6+ sigma for {cat} account. Z-score > 6.0.",
        True, "Unusual amount"
    ))

# ---- 22. UNUSUAL FLOW ----
print("  22. Unusual flow (vendor historical deviation)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS[40:])  # small vendors
    amount = round(random.uniform(1500000, 5000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d,
        random.choice(CATEGORIES[:4]),
        f"Unusual flow: INR {amount:,.2f} is 100x above historical average for vendor {vendor}.",
        True, "Unusual flow"
    ))

# ---- 23. RARE FLOW ----
print("  23. Rare flow (unprecedented account-vendor pairing)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    # Travel vendor booked under Raw Materials
    vendor = random.choice(["MakeMyTrip Ltd", "IndiGo Airlines", "Air India Ltd", "OYO Rooms"])
    amount = round(random.uniform(50000, 300000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d,
        "Raw Materials",
        f"Rare flow: Travel vendor '{vendor}' booked under Raw Materials GL account. Misclassification risk.",
        True, "Rare flow"
    ))

# ---- 24. CASH-PAYMENT RISK ----
print("  24. Cash-payment risk")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = round(random.uniform(100000, 500000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS), d,
        random.choice(CATEGORIES[:4]),
        f"Cash payment risk: INR {amount:,.2f} disbursed in cash. Violates corporate electronic payment mandate.",
        True, "Cash-payment risk"
    ))

# ---- 25. REVERSAL RISK ----
print("  25. Reversal risk (unlinked credit note)")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("Manager", "Sr. Manager")])
    amount = round(random.uniform(500000, 3000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[:10]), d,
        "Miscellaneous",
        f"Reversal risk: Credit note of INR {amount:,.2f} posted without reference to original transaction ID.",
        True, "Reversal risk"
    ))

# ---- 26. HIGH MONETARY VALUE ----
print("  26. High monetary value (top percentile)")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("CEO", "CFO", "CTO", "VP")])
    amount = round(random.uniform(20000000, 80000000), 2)
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[:5]), d,
        random.choice(CATEGORIES[:3]),
        f"Top 0.1% disbursement: INR {amount:,.2f}. Mandatory board-level audit validation required.",
        True, "High monetary value"
    ))

# ---- 27. EXPENSE AND CORPORATE-CARD FRAUD ----
print("  27. Expense and corporate-card fraud")
personal_items = [
    "Personal holiday resort package booking", "Luxury spa and wellness retreat",
    "Family dinner at 5-star restaurant", "Personal Amazon shopping order",
    "Designer clothing purchase at Shoppers Stop", "Personal Uber rides (non-business)",
    "Netflix/Spotify annual subscription", "Personal gym membership renewal",
]
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = round(random.uniform(5000, 50000), 2)
    d = random_weekday_date()
    item = random.choice(personal_items)
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[30:]), d,
        "Travel & Entertainment",
        f"Corporate card fraud: '{item}' filed under business travel expenses.",
        True, "Expense and corporate-card fraud"
    ))

# ---- 28. BENFORD'S LAW ANOMALIES ----
print("  28. Benford's Law anomalies")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    # Force leading digits 7, 8, 9
    leading = random.choice([7, 8, 9])
    rest = random.randint(10000, 99999)
    amount = float(f"{leading}{rest}")
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS), d,
        random.choice(CATEGORIES[:6]),
        f"Benford's Law deviation: Leading digit {leading} over-represented in this vendor cohort.",
        True, "Benford's Law anomalies"
    ))

# ---- 29. WEEKEND AND AFTER-HOURS POSTING ----
print("  29. Weekend and after-hours posting")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = round(random.uniform(10000, 200000), 2)
    # Force weekend
    while True:
        d = random_date()
        if d.weekday() in (5, 6):
            break
    hour = random.choice([0, 1, 2, 3, 4, 23])
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS), d,
        random.choice(CATEGORIES[:4]),
        f"Weekend/after-hours: Transaction on {d.strftime('%A')} at {hour:02d}:{random.randint(0,59):02d}. Outside business hours.",
        True, "Weekend and after-hours posting"
    ))

# ---- 30. SUSPICIOUS WORDING ----
print("  30. Suspicious wording in narration")
suspicious_phrases = [
    "off-the-books", "facilitation payment", "undisclosed commission",
    "personal arrangement", "cash incentive", "kickback adjustment",
    "side deal", "under-the-table", "informal settlement",
]
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = round(random.uniform(50000, 500000), 2)
    d = random_weekday_date()
    phrase = random.choice(suspicious_phrases)
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[:15]), d,
        random.choice(CATEGORIES[:4]),
        f"High-risk narration keyword: '{phrase}' detected in transaction description.",
        True, "Suspicious wording"
    ))

# ---- 31. SEQUENCE GAPS ----
print("  31. Sequence gaps (invoice numbering)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    vendor = random.choice(VERIFIED_VENDORS[:10])
    amount = round(random.uniform(50000, 300000), 2)
    d = random_weekday_date()
    gap = random.randint(500, 2000)
    inv_num = random.randint(100000, 999999)
    rows.append(make_row(
        next_claim_id(), emp, amount, vendor, d,
        random.choice(CATEGORIES[:4]),
        f"Invoice sequence gap: INV-{vendor[:2].upper()}-{inv_num} skips {gap}+ numbers in sequential billing.",
        True, "Sequence gaps"
    ))

# ---- 32. ROUND-NUMBER MANIPULATION ----
print("  32. Round-number or last-digit manipulation")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = random.choice([50000, 100000, 200000, 500000, 1000000, 2000000, 5000000])
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, float(amount), random.choice(VERIFIED_VENDORS[:10]), d,
        "Consulting & Professional Fees",
        f"Round-number anomaly: Exact payment of INR {amount:,} with no decimal itemization.",
        True, "Round-number or last-digit manipulation"
    ))

# ---- 33. MISSING INFORMATION / ERRORS ----
print("  33. Missing information / unintentional errors")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    d = random_weekday_date()
    error_type = random.choice(["zero_amount", "blank_vendor", "no_description"])
    if error_type == "zero_amount":
        rows.append(make_row(next_claim_id(), emp, 0.0, random.choice(VERIFIED_VENDORS), d,
                             "", "Data error: Zero amount transaction. Missing billing details.",
                             True, "Missing information / unintentional errors"))
    elif error_type == "blank_vendor":
        rows.append(make_row(next_claim_id(), emp, round(random.uniform(1000, 50000), 2), "", d,
                             "", "Data error: Blank vendor name and empty category.",
                             True, "Missing information / unintentional errors"))
    else:
        rows.append(make_row(next_claim_id(), emp, round(random.uniform(1000, 50000), 2),
                             random.choice(VERIFIED_VENDORS), d, "",
                             "", True, "Missing information / unintentional errors"))

# ---- 34. EXCESSIVE EMPLOYEE REIMBURSEMENTS ----
print("  34. Excessive employee reimbursements")
for i in range(COUNT_PER_TYPE):
    emp = random.choice([e for e in EMPLOYEES if e["role"] in ("Analyst", "Manager")])
    amount = round(random.uniform(35000, 60000), 2)  # near manager limit
    d = random_weekday_date()
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS[30:]), d,
        "Travel & Entertainment",
        f"Excessive reimbursement: {emp['name']} claimed INR {amount:,.2f}, significantly above peer average of INR 8,000.",
        True, "Excessive employee reimbursements"
    ))

# ---- 35. MIDNIGHT PAYMENTS ----
print("  35. Midnight payments (after-hours authorization)")
for i in range(COUNT_PER_TYPE):
    emp = random_employee()
    amount = round(random.uniform(20000, 300000), 2)
    d = random_weekday_date()
    hour = random.choice([23, 0, 1, 2, 3])
    minute = random.randint(0, 59)
    rows.append(make_row(
        next_claim_id(), emp, amount, random.choice(VERIFIED_VENDORS), d,
        random.choice(CATEGORIES[:4]),
        f"Midnight authorization at {hour:02d}:{minute:02d}. Potential unauthorized access or automated script.",
        True, "Midnight payments"
    ))

# ============================================================================
# SHUFFLE AND WRITE
# ============================================================================

random.shuffle(rows)
print(f"\nTotal records: {len(rows)}")
print(f"  Normal: {sum(1 for r in rows if not r['is_fraud'])}")
print(f"  Anomalous: {sum(1 for r in rows if r['is_fraud'])}")

# Count by type
from collections import Counter
fraud_counts = Counter(r["fraud_type"] for r in rows if r["is_fraud"])
print(f"\nAnomaly types: {len(fraud_counts)}")
for ft, count in sorted(fraud_counts.items(), key=lambda x: -x[1]):
    print(f"  {ft}: {count}")

# Write CSV
fieldnames = ["claim_id", "employee_id", "employee_name", "claimed_amount",
              "vendor_name", "claimed_date", "category", "description",
              "is_fraud", "fraud_type", "ocr_amount", "ocr_vendor", "ocr_confidence"]

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Dataset saved to: {OUTPUT_FILE}")
print(f"   Upload this file to the AuditAI website at http://localhost:5173/upload")
