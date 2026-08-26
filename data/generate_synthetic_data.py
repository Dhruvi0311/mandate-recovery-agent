"""
Synthetic Data Generator — Mandate Recovery Agent
====================================================
Generates 4 linked CSVs simulating AA-consented financial data:
  1. customers.csv          - income profile per customer
  2. transactions.csv       - 90-day transaction history (drives balance patterns)
  3. mandates.csv           - recurring UPI AutoPay obligations
  4. mandate_attempts.csv   - failure/retry events (ground-truth ties to real balance)

Design principle: failures aren't randomly labeled — they emerge from actually
simulating each customer's balance over time and checking it against the mandate
amount on the scheduled date. This makes the "recovery probability" prediction
task genuinely learnable (and genuinely checkable by a skeptical judge).
"""

import random
import csv
from datetime import date, timedelta

random.seed(42)

NUM_CUSTOMERS = 120
SIM_DAYS = 90
START_DATE = date(2026, 6, 1)

MERCHANTS = [
    ("Netflix", 199, "monthly"),
    ("Zomato Gold", 299, "monthly"),
    ("Cult.fit Gym", 1499, "monthly"),
    ("LIC Premium", 2499, "monthly"),
    ("SIP - Mutual Fund", 5000, "monthly"),
    ("Bike Loan EMI", 3200, "monthly"),
    ("Personal Loan EMI", 8500, "monthly"),
    ("Jio Fiber", 999, "monthly"),
    ("Spotify Premium", 119, "monthly"),
    ("Health Insurance", 1850, "monthly"),
]

INCOME_TYPES = [
    ("salaried_fixed", 0.55),
    ("salaried_variable", 0.20),
    ("gig_irregular", 0.18),
    ("business_owner", 0.07),
]

FAILURE_REASONS = ["insufficient_balance", "technical_failure", "mandate_revoked", "account_issue"]


def weighted_choice(pairs):
    r = random.random()
    cum = 0
    for val, w in pairs:
        cum += w
        if r <= cum:
            return val
    return pairs[-1][0]


def gen_customers():
    customers = []
    for i in range(1, NUM_CUSTOMERS + 1):
        income_type = weighted_choice(INCOME_TYPES)

        if income_type == "salaried_fixed":
            avg_income = random.randint(25000, 90000)
            income_day = random.choice([1, 1, 1, 7, 28, 30])  # most common: 1st
            bal_low, bal_high = int(avg_income * 0.05), int(avg_income * 0.35)
        elif income_type == "salaried_variable":
            avg_income = random.randint(22000, 70000)
            income_day = random.randint(3, 10)  # arrives within a window, not fixed
            bal_low, bal_high = int(avg_income * 0.04), int(avg_income * 0.30)
        elif income_type == "gig_irregular":
            avg_income = random.randint(15000, 45000)
            income_day = None  # no fixed anchor — multiple small irregular credits
            bal_low, bal_high = int(avg_income * 0.02), int(avg_income * 0.20)
        else:  # business_owner
            avg_income = random.randint(30000, 150000)
            income_day = None  # lumpy, irregular, larger amounts
            bal_low, bal_high = int(avg_income * 0.03), int(avg_income * 0.40)

        customers.append({
            "customer_id": f"CUST{i:04d}",
            "income_type": income_type,
            "avg_monthly_income": avg_income,
            "income_day_of_month": income_day if income_day else "",
            "avg_balance_low": bal_low,
            "avg_balance_high": bal_high,
            "account_age_months": random.randint(2, 48),
        })
    return customers


def simulate_balance_and_transactions(cust):
    """Simulate day-by-day balance over SIM_DAYS, generating realistic
    credits/debits. Returns (transactions_list, balance_by_date dict)."""
    txns = []
    balance = random.randint(cust["avg_balance_low"], cust["avg_balance_high"])
    balance_by_date = {}
    txn_counter = 1
    income_type = cust["income_type"]

    for d in range(SIM_DAYS):
        cur_date = START_DATE + timedelta(days=d)
        day_of_month = cur_date.day

        # --- Income credits ---
        credited = False
        if income_type in ("salaried_fixed",) and day_of_month == cust["income_day_of_month"]:
            amt = int(cust["avg_monthly_income"] * random.uniform(0.98, 1.02))
            balance += amt
            txns.append((txn_counter, cust["customer_id"], cur_date, "credit", "salary", amt, balance))
            txn_counter += 1
            credited = True
        elif income_type == "salaried_variable" and day_of_month == cust["income_day_of_month"] + random.choice([-1, 0, 0, 1, 2]):
            amt = int(cust["avg_monthly_income"] * random.uniform(0.95, 1.05))
            balance += amt
            txns.append((txn_counter, cust["customer_id"], cur_date, "credit", "salary", amt, balance))
            txn_counter += 1
            credited = True
        elif income_type == "gig_irregular" and random.random() < 0.10:
            amt = int(cust["avg_monthly_income"] / 6 * random.uniform(0.5, 1.8))
            balance += amt
            txns.append((txn_counter, cust["customer_id"], cur_date, "credit", "gig_payout", amt, balance))
            txn_counter += 1
            credited = True
        elif income_type == "business_owner" and random.random() < 0.06:
            amt = int(cust["avg_monthly_income"] / 4 * random.uniform(0.6, 2.2))
            balance += amt
            txns.append((txn_counter, cust["customer_id"], cur_date, "credit", "transfer_in", amt, balance))
            txn_counter += 1
            credited = True

        # --- Routine expenses (drain balance realistically) ---
        if random.random() < 0.35:
            cat = random.choice(["groceries", "utility_bill", "p2p", "entertainment"])
            amt = random.randint(150, 2500)
            if balance - amt > 0:  # no overdraft — small debits only clear if funds cover them
                balance -= amt
                txns.append((txn_counter, cust["customer_id"], cur_date, "debit", cat, amt, balance))
                txn_counter += 1

        if day_of_month in (5, 20) and random.random() < 0.5:
            amt = random.randint(3000, 12000)
            if balance - amt > 0:  # rent only goes through if funds actually cover it
                balance -= amt
                txns.append((txn_counter, cust["customer_id"], cur_date, "debit", "rent", amt, balance))
                txn_counter += 1

        balance_by_date[cur_date] = balance

    return txns, balance_by_date


def gen_mandates(customers):
    mandates = []
    mandate_id = 1
    cust_mandates_map = {}
    for cust in customers:
        n_mandates = random.choice([1, 1, 2, 2, 3])
        chosen = random.sample(MERCHANTS, n_mandates)
        cust_mandates_map[cust["customer_id"]] = []
        for merchant, amt, freq in chosen:
            due_day = random.randint(1, 28)
            status = weighted_choice([("active", 0.85), ("paused", 0.08), ("revoked", 0.07)])
            m = {
                "mandate_id": f"MNDT{mandate_id:04d}",
                "customer_id": cust["customer_id"],
                "merchant_name": merchant,
                "amount": amt,
                "frequency": freq,
                "due_day_of_month": due_day,
                "status": status,
            }
            mandates.append(m)
            cust_mandates_map[cust["customer_id"]].append(m)
            mandate_id += 1
    return mandates, cust_mandates_map


def gen_attempts(customers, cust_mandates_map, cust_balances):
    attempts = []
    attempt_id = 1
    for cust in customers:
        cid = cust["customer_id"]
        balance_by_date = cust_balances[cid]
        for m in cust_mandates_map[cid]:
            if m["status"] != "active":
                continue
            # find scheduled dates within sim window matching due_day_of_month
            for d in range(SIM_DAYS):
                cur_date = START_DATE + timedelta(days=d)
                if cur_date.day != m["due_day_of_month"]:
                    continue

                attempt_num = 1
                resolved = False
                probe_date = cur_date
                while not resolved and attempt_num <= 3:
                    bal = balance_by_date.get(probe_date)
                    if bal is None:
                        break
                    amount_required = m["amount"]

                    # inject occasional non-balance failures for realism
                    fluke = random.random()
                    if fluke < 0.04:
                        status, reason = "failed", "technical_failure"
                    elif fluke < 0.06:
                        status, reason = "failed", "account_issue"
                    elif bal >= amount_required:
                        status, reason = "success", ""
                    else:
                        status, reason = "failed", "insufficient_balance"

                    attempts.append({
                        "attempt_id": f"ATMPT{attempt_id:05d}",
                        "mandate_id": m["mandate_id"],
                        "customer_id": cid,
                        "merchant_name": m["merchant_name"],
                        "scheduled_date": cur_date.isoformat(),
                        "attempt_date": probe_date.isoformat(),
                        "attempt_number": attempt_num,
                        "amount_required": amount_required,
                        "balance_at_attempt": bal,
                        "status": status,
                        "failure_reason": reason,
                    })
                    attempt_id += 1

                    if status == "success":
                        resolved = True
                    else:
                        # blind retry after 2 days (mimics today's naive systems)
                        probe_date = probe_date + timedelta(days=2)
                        attempt_num += 1
    return attempts


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    customers = gen_customers()

    all_txns = []
    cust_balances = {}
    for cust in customers:
        txns, balance_by_date = simulate_balance_and_transactions(cust)
        cust_balances[cust["customer_id"]] = balance_by_date
        for t in txns:
            all_txns.append({
                "transaction_id": f"TXN{t[0]:06d}_{t[1]}",
                "customer_id": t[1],
                "date": t[2].isoformat(),
                "type": t[3],
                "category": t[4],
                "amount": t[5],
                "balance_after": t[6],
            })

    mandates, cust_mandates_map = gen_mandates(customers)
    attempts = gen_attempts(customers, cust_mandates_map, cust_balances)

    write_csv("/mnt/user-data/outputs/customers.csv", customers,
              ["customer_id", "income_type", "avg_monthly_income", "income_day_of_month",
               "avg_balance_low", "avg_balance_high", "account_age_months"])

    write_csv("/mnt/user-data/outputs/transactions.csv", all_txns,
              ["transaction_id", "customer_id", "date", "type", "category", "amount", "balance_after"])

    write_csv("/mnt/user-data/outputs/mandates.csv", mandates,
              ["mandate_id", "customer_id", "merchant_name", "amount", "frequency",
               "due_day_of_month", "status"])

    write_csv("/mnt/user-data/outputs/mandate_attempts.csv", attempts,
              ["attempt_id", "mandate_id", "customer_id", "merchant_name", "scheduled_date",
               "attempt_date", "attempt_number", "amount_required", "balance_at_attempt",
               "status", "failure_reason"])

    print(f"customers: {len(customers)}")
    print(f"transactions: {len(all_txns)}")
    print(f"mandates: {len(mandates)}")
    print(f"mandate_attempts: {len(attempts)}")
    failed = [a for a in attempts if a["status"] == "failed"]
    print(f"failed attempts: {len(failed)} ({len(failed)/len(attempts)*100:.1f}%)")
    reasons = {}
    for a in failed:
        reasons[a["failure_reason"]] = reasons.get(a["failure_reason"], 0) + 1
    print("failure reason breakdown:", reasons)


if __name__ == "__main__":
    main()
