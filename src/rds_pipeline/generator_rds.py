import random
import uuid
from datetime import date, timedelta
from typing import Dict, Optional

import pandas as pd
from faker import Faker

fake = Faker()


def generate_synthetic_demo_data(scale: int = 100, id_offsets: Optional[Dict[str, int]] = None) -> Dict[str, pd.DataFrame]:
    """Generate synthetic data for the RDS schema.

    ``id_offsets`` allows callers (e.g. append mode) to shift starting
    primary key values per table so we can safely append without
    colliding with existing numeric IDs.
    """

    data: Dict[str, pd.DataFrame] = {}

    if id_offsets is None:
        id_offsets = {}

    countries = [
        {"country_code": "US", "country_name": "United States", "iso3_code": "USA"},
        {"country_code": "CA", "country_name": "Canada", "iso3_code": "CAN"},
        {"country_code": "GB", "country_name": "United Kingdom", "iso3_code": "GBR"},
    ]
    for c in countries:
        c["created_at"] = fake.date_time_between(start_date="-5y", end_date="now")
    data["country"] = pd.DataFrame(countries)

    states = []
    state_id = 1
    used_state_codes = {c["country_code"]: set() for c in countries}

    for c in countries:
        for _ in range(3):
            for _ in range(10):
                code = fake.state_abbr()
                if code not in used_state_codes[c["country_code"]]:
                    used_state_codes[c["country_code"]].add(code)
                    break

            states.append(
                {
                    "state_id": state_id,
                    "country_code": c["country_code"],
                    "state_code": code,
                    "state_name": fake.state(),
                    "is_active": True,
                }
            )
            state_id += 1
    data["state_province"] = pd.DataFrame(states)

    contact_types = [
        {"contact_type_code": "HOME", "description": "Home"},
        {"contact_type_code": "WORK", "description": "Work"},
        {"contact_type_code": "BILLING", "description": "Billing"},
        {"contact_type_code": "SHIPPING", "description": "Shipping"},
    ]
    data["contact_type"] = pd.DataFrame(contact_types)

    party_rows = []
    person_rows = []
    org_rows = []

    n_person = scale
    n_org = max(scale // 5, 1)

    for _ in range(n_person):
        pid = uuid.uuid4()
        party_rows.append(
            {
                "party_id": pid,
                "party_type": "PERSON",
                "created_at": fake.date_time_between(start_date="-5y", end_date="now"),
                "updated_at": None,
                "is_active": random.choice([True, True, False]),
            }
        )
        person_rows.append(
            {
                "party_id": pid,
                "first_name": fake.first_name(),
                "middle_name": None,
                "last_name": fake.last_name(),
                "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=90),
                "gender": random.choice(["MALE", "FEMALE", "NON_BINARY", "OTHER"]),
                "ssn": fake.ssn(),
            }
        )

    for _ in range(n_org):
        pid = uuid.uuid4()
        party_rows.append(
            {
                "party_id": pid,
                "party_type": "ORGANIZATION",
                "created_at": fake.date_time_between(start_date="-10y", end_date="now"),
                "updated_at": None,
                "is_active": True,
            }
        )
        org_rows.append(
            {
                "party_id": pid,
                "legal_name": fake.company(),
                "trade_name": fake.company_suffix(),
                "tax_id": fake.bothify(text="##-#######"),
                "incorporation_date": fake.date_between(start_date="-30y", end_date="-1y"),
            }
        )

    data["party"] = pd.DataFrame(party_rows)
    data["person"] = pd.DataFrame(person_rows)
    data["organization"] = pd.DataFrame(org_rows)

    addresses = []
    emails = []
    phones = []

    address_id = id_offsets.get("address_id", 1)
    email_id = id_offsets.get("email_id", 1)
    phone_id = id_offsets.get("phone_id", 1)

    all_parties = [row["party_id"] for row in party_rows]
    states_df = data["state_province"]

    for pid in all_parties:
        for _ in range(random.randint(1, 2)):
            row_state = states_df.sample(1).iloc[0]
            addresses.append(
                {
                    "address_id": address_id,
                    "party_id": pid,
                    "line1": fake.street_address(),
                    "line2": None,
                    "city": fake.city(),
                    "state_id": int(row_state["state_id"]),
                    "postal_code": fake.postcode(),
                    "country_code": row_state["country_code"],
                    "is_primary": False,
                    "valid_from": date.today() - timedelta(days=random.randint(0, 3650)),
                    "valid_to": None,
                }
            )
            address_id += 1

        emails.append(
            {
                "email_id": email_id,
                "party_id": pid,
                "email": fake.email(),
                "is_primary": True,
                "contact_type_code": random.choice(["HOME", "WORK"]),
            }
        )
        email_id += 1

        phones.append(
            {
                "phone_id": phone_id,
                "party_id": pid,
                "phone_number": "+1" + fake.msisdn()[0:10],
                "is_primary": True,
                "contact_type_code": random.choice(["HOME", "WORK"]),
            }
        )
        phone_id += 1

    data["address"] = pd.DataFrame(addresses)
    data["email_address"] = pd.DataFrame(emails)
    data["phone_number"] = pd.DataFrame(phones)

    departments = []
    for dept_id in range(1, 6):
        departments.append(
            {
                "department_id": dept_id,
                "department_code": f"D{dept_id:03d}",
                "department_name": f"Department {dept_id}",
                "manager_party_id": random.choice(all_parties),
                "budget": round(random.uniform(10_000, 1_000_000), 2),
                "created_at": fake.date_time_between(start_date="-5y", end_date="now"),
            }
        )
    data["department"] = pd.DataFrame(departments)

    employees = []
    employee_id = 1
    employment_types = ["FULL_TIME", "PART_TIME", "CONTRACTOR"]
    person_party_ids = [row["party_id"] for row in person_rows]

    for pid in random.sample(person_party_ids, min(len(person_party_ids), scale)):
        etype = random.choice(employment_types)
        hire_date = fake.date_between(start_date="-10y", end_date="-1y")
        term_date = None
        if random.random() < 0.2:
            term_date = fake.date_between(start_date=hire_date, end_date="today")

        annual_salary = None
        hourly_rate = None
        if etype in ("FULL_TIME", "PART_TIME"):
            annual_salary = round(random.uniform(40_000, 200_000), 2)
        else:
            hourly_rate = round(random.uniform(30, 200), 2)

        employees.append(
            {
                "employee_id": employee_id,
                "party_id": pid,
                "department_id": random.randint(1, 5),
                "hire_date": hire_date,
                "termination_date": term_date,
                "employment_type": etype,
                "annual_salary": annual_salary,
                "hourly_rate": hourly_rate,
            }
        )
        employee_id += 1

    data["employee"] = pd.DataFrame(employees)

    projects = []
    project_id = id_offsets.get("project_id", 1)
    for _ in range(max(scale // 10, 5)):
        start = fake.date_between(start_date="-5y", end_date="today")
        end = None
        if random.random() < 0.5:
            end = fake.date_between(start_date=start, end_date="+1y")
        projects.append(
            {
                "project_id": project_id,
                "project_code": f"P{project_id:05d}",
                "project_name": fake.bs().title(),
                "owning_department": random.randint(1, 5),
                "start_date": start,
                "end_date": end,
                "budget": round(random.uniform(50_000, 5_000_000), 2),
                "is_active": end is None,
                "metadata": None,
            }
        )
        project_id += 1

    data["project"] = pd.DataFrame(projects)

    products = []
    # Ensure product_id and sku are unique and stable for any scale.
    num_products = max(scale // 10, 20)
    start_product_id = id_offsets.get("product_id", 1)
    for i in range(num_products):
        product_id = start_product_id + i
        products.append(
            {
                "product_id": product_id,
                "sku": f"SKU-{product_id:04d}",
                "product_name": fake.word().title(),
                "description": fake.sentence(),
                "base_price": round(random.uniform(5, 500), 2),
                "tags": None,
                "attributes": None,
                "created_at": fake.date_time_between(start_date="-3y", end_date="now"),
                "discontinued_at": None,
            }
        )

    data["product"] = pd.DataFrame(products)

    customers = []
    customer_id = id_offsets.get("customer_id", 1)
    for pid in random.sample(all_parties, min(len(all_parties), scale)):
        customers.append(
            {
                "customer_id": customer_id,
                "party_id": pid,
                "customer_since": fake.date_between(start_date="-10y", end_date="today"),
                "credit_limit": round(random.uniform(0, 50_000), 2),
                "risk_score": round(random.uniform(0, 1), 3),
                "loyalty_tier": random.choice(["BRONZE", "SILVER", "GOLD", "PLATINUM"]),
            }
        )
        customer_id += 1

    data["customer"] = pd.DataFrame(customers)

    addr_df = data["address"]
    primary_addr_by_party = addr_df.groupby("party_id")["address_id"].first().to_dict()

    order_headers = []
    order_lines = []
    payments = []

    order_id = id_offsets.get("order_id", 1)
    line_number = 1
    payment_id = id_offsets.get("payment_id", 1)

    for cust in customers:
        for _ in range(random.randint(1, 3)):
            placed_at = fake.date_time_between(start_date="-2y", end_date="now")
            billing_addr_id = primary_addr_by_party.get(cust["party_id"])
            shipping_addr_id = billing_addr_id
            order_currency = random.choice(["USD", "CAD", "GBP"])

            order_headers.append(
                {
                    "order_id": order_id,
                    "customer_id": cust["customer_id"],
                    "billing_address_id": billing_addr_id,
                    "shipping_address_id": shipping_addr_id,
                    "order_status": random.choice(
                        ["PENDING", "PAID", "SHIPPED", "CANCELLED", "RETURNED"]
                    ),
                    "order_total": 0.0,
                    "currency_code": order_currency,
                    "placed_at": placed_at,
                    "shipped_at": None,
                    "cancelled_at": None,
                }
            )

            order_total = 0.0
            for _ in range(random.randint(1, 5)):
                prod = random.choice(products)
                qty = random.randint(1, 5)
                unit_price = prod["base_price"]
                discount = 0.0
                line_total = qty * unit_price - discount
                order_lines.append(
                    {
                        "order_id": order_id,
                        "line_number": line_number,
                        "product_id": prod["product_id"],
                        "quantity": qty,
                        "unit_price": unit_price,
                        "discount_amount": discount,
                        "line_total": line_total,
                    }
                )
                line_number += 1
                order_total += line_total

            payments.append(
                {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "payment_method": random.choice(
                        ["CARD", "BANK_TRANSFER", "CASH", "VOUCHER"]
                    ),
                    "amount": round(order_total, 2),
                    "paid_at": fake.date_time_between(start_date=placed_at, end_date="now"),
                    "transaction_ref": fake.uuid4(),
                    "is_refund": False,
                }
            )
            payment_id += 1

            order_headers[-1]["order_total"] = round(order_total, 2)
            order_id += 1

    data["order_header"] = pd.DataFrame(order_headers)
    data["order_line"] = pd.DataFrame(order_lines)
    data["payment"] = pd.DataFrame(payments)

    audits = []
    audit_id = id_offsets.get("audit_id", 1)
    for oh in order_headers[: max(10, scale // 10)]:
        audits.append(
            {
                "audit_id": audit_id,
                "entity_type": "order_header",
                "entity_id": str(oh["order_id"]),
                "operation": random.choice(["INSERT", "UPDATE"]),
                "performed_by": None,
                "performed_at": fake.date_time_between(start_date="-1y", end_date="now"),
                "data_before": None,
                "data_after": None,
            }
        )
        audit_id += 1

    data["audit_log"] = pd.DataFrame(audits)

    documents = []
    document_id = id_offsets.get("document_id", 1)
    for pid in random.sample(all_parties, min(len(all_parties), max(5, scale // 20))):
        documents.append(
            {
                "document_id": document_id,
                "owner_party_id": pid,
                "filename": fake.file_name(),
                "mime_type": "application/octet-stream",
                "content": fake.binary(length=128),
            }
        )
        document_id += 1

    data["document_store"] = pd.DataFrame(documents)

    return data
