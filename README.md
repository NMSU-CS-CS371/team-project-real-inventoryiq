# InventoryIQ

Inventory management web app for small businesses. Built for CS 3710 (Spring 2026) by Alex, Lalo, and Cesar.

The idea is to give a small business owner a simple way to track what they have in stock, get notified when something runs low, and keep an eye on basic financials — without needing to know anything about software.

---

## What it does

- Add, edit, and delete products with SKUs, quantities, and cost/retail pricing
- Organize products into categories (supports subcategories)
- Dashboard showing inventory value, profit estimates, and low-stock items
- Low-stock email alerts sent automatically via Gmail when quantity drops below a per-product threshold
- Purchase orders to track incoming stock from suppliers
- Finances page with expense tracking, debt accounts, and monthly budget
- CSV export of all products
- All views are behind login — one user account per instance

---

## Repo structure

```
team-project-real-inventoryiq/
├── inventory/          Main Django app — models, views, forms, URLs
├── inventoryiq/        Project config — settings.py, root urls.py
├── templates/          HTML templates (base.html + inventory/*.html)
├── manage.py           Django CLI entry point
├── requirements.txt    Python dependencies
├── .env.example        Template for your .env file
└── db.sqlite3          Dev database — pre-seeded with some test data
```

`venv/` and `__pycache__/` will show up after setup — those are generated and can be ignored.

---

## Requirements

- Python 3.10+
- pip

---

## Setup

```bash
# Clone the repo and cd into the project folder
cd team-project-real-inventoryiq

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up your environment file
cp .env.example .env
# Open .env and fill in SECRET_KEY at minimum (see Config section below)

# Run migrations
python manage.py migrate

# Create a login account
python manage.py createsuperuser
```

---

## Running it

```bash
python manage.py runserver
```

Then open http://127.0.0.1:8000 in a browser and log in with the account you just created.

---

## Config

All config goes in `.env`. The `.env.example` file shows what's available.

**Required:**
- `SECRET_KEY` — any long random string. You can generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_hex(50))"
  ```

**Email alerts (optional):**

Low-stock alerts are sent via Gmail SMTP. To enable them:

1. Go to your Google account → Security → 2-Step Verification (must be on)
2. Go to App Passwords and generate one for "Mail"
3. Put that 16-character password (not your regular Gmail password) in `.env`:

```
EMAIL_USER=your@gmail.com
EMAIL_PASSWORD=your-app-password
LOW_STOCK_EMAIL=where-to-send-alerts@example.com
```

If these aren't set, the app still works — alerts just won't send.


