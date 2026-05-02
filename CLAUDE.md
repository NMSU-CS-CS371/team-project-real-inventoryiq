# InventoryIQ — CLAUDE.md

## Project Overview

**InventoryIQ** is an inventory management system designed for small business owners who are not tech-savvy. The goal is to make tracking stock, products, and quantities as simple as possible.

**Team:** Lalo, Alex, Cesar
**Course:** CS3710

### Target Users
- Small business owners with limited tech experience
- Prioritize simplicity and clarity over advanced features
- UI should be intuitive — minimal onboarding needed

### Platform
- Preferred: Mobile app (React Native or similar)
- Acceptable fallback: Responsive web app
- Decision TBD — update this file once confirmed

---

## Tech Stack

- **Backend:** Python 3.10 + Django 4.1.7
- **Database:** SQLite (development) → PostgreSQL (production)
- **Frontend:** Django templates + Bootstrap 5 (mobile-responsive web app)
- **Auth:** Django built-in authentication

---

## Project Structure

```
/
├── CLAUDE.md
├── README.md
├── manage.py              # Django CLI
├── requirements.txt
├── .env                   # Local secrets (not committed)
├── .env.example           # Template for .env
├── inventoryiq/           # Django project config
│   ├── settings.py
│   └── urls.py
├── inventory/             # Main app
│   ├── models.py          # Product, Category
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── migrations/
└── templates/
    ├── base.html
    ├── registration/login.html
    └── inventory/
        ├── dashboard.html
        ├── product_list.html
        ├── product_form.html
        └── product_confirm_delete.html
```

---

## Dev Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then edit .env with your values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Default dev login: `admin` / `admin123`
App runs at: http://127.0.0.1:8000

---

## Key Features to Build

- [ ] Add / edit / delete products
- [ ] Track stock quantities
- [ ] Low-stock alerts
- [ ] Simple dashboard (total items, low stock count)
- [ ] User authentication (business owner login)
- [ ] (Stretch) Barcode scanning

---

## Design Principles

1. **Simple first** — every screen should be usable without instructions
2. **Mobile-friendly** — large touch targets, minimal text input
3. **Fast** — small business owners are busy; keep interactions short
4. **Offline-friendly** — consider local-first or offline support if time allows

---

## Coding Standards

> Update with team-agreed conventions once stack is set.

- Keep components/functions small and focused
- Write clear variable names (no abbreviations)
- Comment non-obvious logic
- No unused code — remove dead code rather than commenting it out

---

## Notes for Claude

- This is a CS3710 team project — suggest solutions appropriate for a semester-scope project
- Prioritize working features over polish
- When suggesting architecture, keep it simple and within the team's skill level
- Tech stack is not yet decided — if asked about it, present trade-offs and let the team decide
