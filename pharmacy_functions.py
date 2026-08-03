import difflib
import os

from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://voiceagent:voiceagent@localhost:5432/voiceagent"
)
MAX_CALLS_PER_DAY = int(os.getenv("MAX_CALLS_PER_DAY", "20"))
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False)


def init_db():
    """Open the DB pool (blocking until Postgres is reachable) and create the schema."""
    pool.open(wait=True, timeout=30)
    with pool.connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                drug_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                total NUMERIC(10, 2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def is_call_allowed():
    """Read-only check of today's demo call cap.

    Safe to call from the unauthenticated /twiml endpoint: it never writes, so
    anonymous requests cannot burn through the quota.
    """
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT count(*) FROM calls WHERE created_at > now() - interval '1 day'"
        ).fetchone()
        return row[0] < MAX_CALLS_PER_DAY


def record_call():
    """Count one demo call. Only ever called after the stream token is validated."""
    with pool.connection() as conn:
        conn.execute("INSERT INTO calls DEFAULT VALUES")


# Prices are in EUR. Catalog is static reference data, not user-generated, so it
# stays in code rather than in the database.
DRUG_DB = {
    "aspirin": {"name": "Acetylsalicylic Acid", "price": 5.49,
                "description": "Non-steroidal anti-inflammatory drug for pain relief and fever reduction",
                "quantity": 30},
    "ibuprofen": {"name": "Ibuprofen", "price": 7.29,
                  "description": "Anti-inflammatory medication for pain and inflammation management", "quantity": 20},
    "acetaminophen": {"name": "Acetaminophen", "price": 6.39,
                      "description": "Analgesic and antipyretic medication for pain and fever control", "quantity": 25},
    "metformin": {"name": "Metformin Hydrochloride", "price": 11.45,
                  "description": "Biguanide antidiabetic medication for type 2 diabetes management", "quantity": 60},
    "lisinopril": {"name": "Lisinopril", "price": 8.00,
                   "description": "ACE inhibitor for hypertension and heart failure treatment", "quantity": 30},
    "atorvastatin": {"name": "Atorvastatin Calcium", "price": 13.99,
                     "description": "HMG-CoA reductase inhibitor for cholesterol management", "quantity": 30},
    "omeprazole": {"name": "Omeprazole", "price": 10.99,
                   "description": "Proton pump inhibitor for acid reflux and ulcer treatment", "quantity": 28},
    "amlodipine": {"name": "Amlodipine Besylate", "price": 8.69,
                   "description": "Calcium channel blocker for hypertension and angina", "quantity": 30},
    "metoprolol": {"name": "Metoprolol Tartrate", "price": 6.65,
                   "description": "Beta-blocker for hypertension and heart rhythm disorders", "quantity": 30},
    "sertraline": {"name": "Sertraline Hydrochloride", "price": 12.59,
                   "description": "Selective serotonin reuptake inhibitor for depression and anxiety", "quantity": 30}
}


def _find_drug(drug_name):
    """Exact match first, falling back to the closest catalog name for misheard input."""
    key = drug_name.lower().strip()
    if key in DRUG_DB:
        return key, DRUG_DB[key]

    matches = difflib.get_close_matches(key, DRUG_DB.keys(), n=1, cutoff=0.6)
    if matches:
        return matches[0], DRUG_DB[matches[0]]

    return None, None


def get_drug_info(drug_name):
    """Get drug information."""
    _, drug = _find_drug(drug_name)
    if drug:
        return {
            "name": drug["name"],
            "description": drug["description"],
            "price": drug["price"],
            "currency": "EUR",
            "quantity": drug["quantity"]
        }
    return {"error": f"Drug '{drug_name}' not found"}


def place_order(customer_name, drug_name, quantity=None):
    """Place an order for the requested quantity (falls back to the drug's predefined quantity)."""
    _, drug = _find_drug(drug_name)
    if not drug:
        return {"error": f"Drug '{drug_name}' not found"}

    if quantity is None:
        quantity = drug["quantity"]
    else:
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return {"error": f"Invalid quantity: {quantity!r}"}
        if quantity <= 0:
            return {"error": "Quantity must be a positive number"}

    total = round(drug["price"] * quantity, 2)

    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO orders (customer_name, drug_name, quantity, total)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (customer_name, drug["name"], quantity, total),
        ).fetchone()
        order_id = row[0]

    return {
        "order_id": order_id,
        "message": f"Order {order_id} placed: {quantity} {drug['name']} for €{total:.2f}",
        "total": total,
        "currency": "EUR",
        "quantity": quantity
    }


def lookup_order(order_id):
    """Look up an order."""
    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        return {"error": f"Invalid order id: {order_id!r}"}

    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT id, customer_name, drug_name, quantity, total, status
            FROM orders WHERE id = %s
            """,
            (order_id_int,),
        ).fetchone()

    if row:
        return {
            "order_id": row[0],
            "customer": row[1],
            "drug": row[2],
            "quantity": row[3],
            "total": float(row[4]),
            "currency": "EUR",
            "status": row[5]
        }
    return {"error": f"Order {order_id} not found"}


# Function mapping dictionary
FUNCTION_MAP = {
    'get_drug_info': get_drug_info,
    'place_order': place_order,
    'lookup_order': lookup_order
}
