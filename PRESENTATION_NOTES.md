# InventoryIQ — Presentation Notes

**Course:** CS3710  
**Team:** Lalo, Alex, Cesar  
**Date:** April 8, 2026

---

## 1. What Is InventoryIQ?

InventoryIQ is a web-based inventory management system built for small business owners who aren't tech-savvy. It lets them track products, monitor stock levels, and get alerts when items are running low — all through a clean, simple interface.

**Problem we're solving:** Small businesses often track inventory with spreadsheets or pen-and-paper, which is error-prone and hard to maintain. InventoryIQ gives them a lightweight, easy-to-use alternative without the complexity of enterprise software.

---

## 2. Tech Stack

| Layer       | Technology                        | Why We Chose It                                      |
|-------------|-----------------------------------|------------------------------------------------------|
| Backend     | Python 3.10 + Django 4.1.7        | Rapid development, built-in admin, auth, and ORM     |
| Frontend    | Django Templates + Bootstrap 5.3  | Mobile-responsive out of the box, no separate frontend needed |
| Database    | SQLite (dev) / PostgreSQL (prod)  | SQLite for easy local setup, PostgreSQL for production scale |
| Email       | Gmail SMTP                        | Free, simple setup for low-stock notifications       |
| Fonts       | Sora + DM Mono (Google Fonts)     | Clean, modern look                                   |

**Key dependencies:** Django, psycopg2-binary (PostgreSQL driver), python-dotenv (environment config), Pillow (image support)

---

## 3. Project Structure

```
inventoryiq/          --> Django project settings (settings.py, urls.py)
inventory/            --> Main app with all the business logic
  models.py           --> Database models (Product, Category)
  views.py            --> All page logic and request handling
  forms.py            --> Form definitions for products and categories
  urls.py             --> App-level URL routing
  utils.py            --> Email notification helper
  admin.py            --> Django admin configuration
  migrations/         --> Database schema changes over time
templates/            --> All HTML templates (10 files)
  base.html           --> Master layout (navbar, styles, structure)
  inventory/          --> Feature-specific pages
  registration/       --> Login page
static/               --> Static assets (logo, images)
manage.py             --> Django command-line tool
requirements.txt      --> Python dependencies
.env                  --> Secret keys and config (not in git)
```

---

## 4. Data Models

### Category
- `name` — the category label (e.g., "Electronics", "Office Supplies")
- Products belong to a category (one-to-many relationship)

### Product
| Field                | Type          | Purpose                                         |
|----------------------|---------------|--------------------------------------------------|
| name                 | Text          | Product name                                     |
| category             | Foreign Key   | Links to a Category (optional)                   |
| quantity             | Positive Int  | Current stock count                              |
| low_stock_threshold  | Positive Int  | When to trigger a low-stock alert (default: 5)   |
| sku_number           | Text (unique) | Stock Keeping Unit identifier                    |
| retail_value         | Decimal       | Price per unit for financial tracking             |
| description          | Text          | Optional product description                     |
| low_stock_notified   | Boolean       | Prevents duplicate email alerts                  |
| created_at           | DateTime      | When the product was added                       |
| updated_at           | DateTime      | Last modification timestamp                      |

**Key logic:** `is_low_stock` property returns True when `quantity <= low_stock_threshold`

---

## 5. Features Walkthrough

### Dashboard (Home Page)
- Shows total number of products and how many are low on stock
- Lists all low-stock products with links to edit them
- Visual alerts (red styling) draw attention to items needing restocking

### Product Management (Full CRUD)
- **Add** a new product with name, SKU, category, quantity, threshold, retail value, and description
- **Edit** any product — updates trigger low-stock checks automatically
- **Delete** with a confirmation page to prevent accidental removal
- Products are displayed **grouped by category** for easy browsing

### Quick Quantity Adjustment
- +1 / -1 buttons on each product for fast stock updates
- Quantity can't go below zero
- Automatically sends low-stock email if quantity drops below threshold

### Search and Filter
- Search bar filters products by name, description, or category
- Dropdown filter to view only products in a specific category

### Category Management
- Create categories to organize products
- View all products within a category
- Add products directly from a category page (pre-fills the category)
- Shows product count per category

### Low-Stock Email Alerts
- When a product's quantity drops to or below its threshold, an email is sent automatically
- Uses Gmail SMTP to notify the business owner
- `low_stock_notified` flag prevents sending duplicate emails
- Flag resets when stock is replenished above the threshold

### Finances Page
- Calculates total inventory value (retail_value x quantity for each product)
- Displays a per-product breakdown in a table
- Shows a grand total at the bottom

### CSV Export
- One-click download of all products as a CSV file
- Includes: Name, SKU, Category, Quantity, Threshold, Description
- Useful for reporting or importing into other tools

### Authentication
- Login/logout with Django's built-in auth system
- All pages require login — unauthenticated users are redirected to login
- Session-based authentication

---

## 6. How It All Connects (Request Flow)

```
User clicks a link or submits a form
        |
        v
  URL Router (urls.py) matches the URL pattern
        |
        v
  View function (views.py) runs the logic:
    - Reads/writes to the database via Models
    - Processes form data if applicable
    - Triggers email alerts if needed
        |
        v
  Template (HTML) renders the response:
    - Extends base.html for consistent layout
    - Uses Bootstrap for responsive styling
        |
        v
  Browser displays the page to the user
```

**Example — adjusting quantity:**
1. User clicks the "+" button on a product
2. URL routes to `adjust_quantity` view
3. View increments the product's quantity in the database
4. View checks if stock crossed the low-stock threshold
5. If low stock: sends email via `utils.py`, sets `low_stock_notified = True`
6. Redirects back to the product list with updated quantity

---

## 7. Design Decisions

- **Django over React/Node:** Faster to build for a semester project. Templates + Bootstrap give us a responsive UI without managing a separate frontend.
- **SQLite + PostgreSQL dual support:** SQLite requires zero setup for development. PostgreSQL config is ready for production via environment variables.
- **Gmail SMTP for alerts:** Free and simple. No need for a paid email service for our use case.
- **Bootstrap 5:** Gives us mobile-friendly, professional-looking UI with minimal custom CSS.
- **Custom color scheme:** Dark navbar (#16150f) with warm, neutral tones — gives the app a clean, modern feel rather than default Bootstrap blue.
- **Login required on everything:** Since this manages business data, every page is protected behind authentication.

---

## 8. Database Evolution (Migrations)

We built the schema incrementally as we added features:

1. **Initial** — Product and Category models with core fields
2. **Added SKU numbers** — unique identifier per product
3. **Added low_stock_notified flag** — prevents duplicate email alerts
4. **Added retail_value** — enables the finances/inventory valuation page

---

## 9. Suggested Demo Flow

If doing a live demo, here's a natural order:

1. **Login** — show the authentication screen
2. **Dashboard** — point out the summary metrics and low-stock alerts
3. **Add a Category** — e.g., "Beverages"
4. **Add a Product** — fill in the form with SKU, quantity, retail value, etc.
5. **Product List** — show how products are grouped by category
6. **Search/Filter** — search for a product, filter by category
7. **Quick Adjust** — click +/- buttons, show quantity updating in real-time
8. **Low-Stock Alert** — reduce a product below its threshold, mention the email notification
9. **Finances** — show inventory valuation with totals
10. **CSV Export** — download the CSV file
11. **Delete a Product** — show the confirmation step

---

## 10. Potential Questions and Answers

**Q: Why not a mobile app?**  
A: We considered React Native but chose a responsive web app for faster development within the semester timeline. The Bootstrap layout works well on mobile browsers.

**Q: How does the email notification work?**  
A: When a product's quantity drops to or below its low_stock_threshold, Django sends an email via Gmail SMTP. A flag prevents duplicate alerts until the stock is replenished.

**Q: Can multiple users use this?**  
A: Yes, Django's auth system supports multiple users. Each user logs in with their own credentials. Currently all users see the same inventory.

**Q: How would you scale this for production?**  
A: Switch the database to PostgreSQL (already configured), set DEBUG=False, configure a proper web server (Gunicorn + Nginx), and use environment variables for all secrets.

**Q: What would you add with more time?**  
A: Barcode scanning, purchase order tracking, multi-location support, role-based permissions, and a REST API for mobile app integration.

---

## 11. UML Class Diagram

> **Note:** The UML class diagram image file should be uploaded separately and embedded here:
> `![UML Class Diagram](uml_class_diagram.png)`

Below is the text representation of the class diagram. Use this to create the image (e.g., in draw.io, Lucidchart, or PlantUML), then embed it above.

```
┌─────────────────────────────────┐
│      django.db.models.Model     │  (Django Framework)
│         «abstract»              │
├─────────────────────────────────┤
│ + pk: int                       │
│ + save()                        │
│ + delete()                      │
│ + objects: Manager              │
└──────────┬──────────┬───────────┘
           │          │
     inherits    inherits
           │          │
┌──────────┴───┐ ┌────┴──────────────────────────┐
│   Category   │ │           Product              │
├──────────────┤ ├───────────────────────────────-─┤
│ + name: str  │ │ + name: str                    │
│              │ │ + category: FK → Category       │
├──────────────┤ │ + quantity: int                 │
│ + __str__()  │ │ + low_stock_threshold: int      │
└──────────────┘ │ + sku_number: str (unique)      │
       ▲         │ + retail_value: Decimal          │
       │         │ + description: str               │
       │ 1       │ + low_stock_notified: bool       │
       │         │ + created_at: DateTime           │
       │         │ + updated_at: DateTime           │
       │         ├────────────────────────────────-─┤
       │         │ + is_low_stock: bool «property»  │
       │         │ + __str__(): str                  │
       │   0..*  └────────────────┬─────────────────┘
       │                          │
       └────── category (FK) ─────┘
           (many-to-one association)


┌─────────────────────────────────┐
│      forms.ModelForm            │  (Django Framework)
│         «abstract»              │
└──────────┬──────────┬───────────┘
           │          │
     inherits    inherits
           │          │
┌──────────┴────────┐ ┌──────────┴────────┐
│   ProductForm     │ │   CategoryForm    │
├───────────────────┤ ├───────────────────┤
│ Meta.model =      │ │ Meta.model =      │
│   Product         │ │   Category        │
│ Meta.fields = [   │ │ Meta.fields = [   │
│   name, sku,      │ │   name            │
│   retail_value,   │ │ ]                 │
│   category,       │ │ Meta.widgets = {} │
│   quantity,       │ └───────────────────┘
│   threshold,      │          │
│   description ]   │          │ uses
│ Meta.widgets = {} │          ▼
└───────────────────┘   ┌──────────┐
         │              │ Category │
         │ uses         └──────────┘
         ▼
   ┌─────────┐
   │ Product │
   └─────────┘


┌─────────────────────────────────┐
│      admin.ModelAdmin           │  (Django Framework)
│         «abstract»              │
└──────────┬──────────┬───────────┘
           │          │
     inherits    inherits
           │          │
┌──────────┴────────┐ ┌──────────┴────────┐
│  ProductAdmin     │ │  CategoryAdmin    │
├───────────────────┤ ├───────────────────┤
│ list_display = [  │ │ list_display = [  │
│   name, category, │ │   name            │
│   quantity,       │ │ ]                 │
│   threshold,      │ └───────────────────┘
│   is_low_stock,   │          │
│   updated_at ]    │          │ registered for
│ list_filter = [   │          ▼
│   category ]      │   ┌──────────┐
│ search_fields = [ │   │ Category │
│   name ]          │   └──────────┘
└───────────────────┘
         │
         │ registered for
         ▼
   ┌─────────┐
   │ Product │
   └─────────┘


┌─────────────────────────────────┐
│     django.contrib.auth.User    │  (Django Framework)
├─────────────────────────────────┤
│ + username: str                 │
│ + password: str                 │
│ + email: str                    │
│ + is_active: bool               │
├─────────────────────────────────┤
│ + authenticate()                │
│ + login()                       │
│ + logout()                      │
└─────────────────────────────────┘
         │
         │ authenticates (association — used by
         │ @login_required decorator on all views)
         ▼
┌─────────────────────────────────┐
│  «module» views.py              │
│  (function-based views)         │
├─────────────────────────────────┤
│ + dashboard(request)            │
│ + product_list(request)         │
│ + product_add(request)          │
│ + product_edit(request, pk)     │
│ + product_delete(request, pk)   │
│ + adjust_quantity(request, pk)  │
│ + category_list(request)        │
│ + category_add(request)         │
│ + category_detail(request, pk)  │
│ + finances(request)             │
│ + export_csv(request)           │
└────────┬──────────┬─────────────┘
         │          │
    uses  │          │  uses
         ▼          ▼
   ┌─────────┐ ┌──────────┐
   │ Product │ │ Category │
   └─────────┘ └──────────┘
         │
         │ uses (calls send_low_stock_email)
         ▼
┌─────────────────────────────────┐
│  «module» utils.py              │
├─────────────────────────────────┤
│ + send_low_stock_email(product) │
│   → uses django.core.mail      │
│   → reads from os.environ      │
│   → mutates product.            │
│     low_stock_notified          │
└─────────────────────────────────┘
```

### Relationship Summary Table

| Relationship | Type | Description |
|---|---|---|
| Product → Category | **Association (Many-to-One)** | Each Product holds a ForeignKey reference to a Category. A Category can have many Products. The FK uses `SET_NULL` on delete, so products survive category deletion. |
| Product → Model | **Inheritance** | Product extends `django.db.models.Model`, gaining ORM capabilities (save, delete, queryset manager). |
| Category → Model | **Inheritance** | Category extends `django.db.models.Model`. |
| ProductForm → ModelForm | **Inheritance** | ProductForm extends `forms.ModelForm`, binding the form to the Product model. |
| CategoryForm → ModelForm | **Inheritance** | CategoryForm extends `forms.ModelForm`, binding the form to the Category model. |
| ProductForm → Product | **Association (uses)** | ProductForm's `Meta.model = Product` — it reads/writes Product instances. |
| CategoryForm → Category | **Association (uses)** | CategoryForm's `Meta.model = Category` — it reads/writes Category instances. |
| ProductAdmin → ModelAdmin | **Inheritance** | ProductAdmin extends `admin.ModelAdmin` to customize the Django admin interface for Products. |
| CategoryAdmin → ModelAdmin | **Inheritance** | CategoryAdmin extends `admin.ModelAdmin` for Categories. |
| views → Product, Category | **Association (uses)** | View functions query and mutate Product and Category objects via the Django ORM. |
| views → ProductForm, CategoryForm | **Association (uses)** | View functions instantiate form objects to handle user input validation and model saving. |
| views → User | **Association (dependency)** | All view functions are decorated with `@login_required`, which checks for an authenticated `User` via Django's session middleware. |
| views → utils.send_low_stock_email | **Association (uses)** | `adjust_quantity` and `product_edit` call `send_low_stock_email()` when stock drops below the threshold. |
| send_low_stock_email → Product | **Association (uses)** | Receives a Product instance, reads its fields, and mutates `low_stock_notified`. |

---

## 12. Class Design Description

### Major Classes and Their Responsibilities

**Category (Model)**
- Represents a product grouping (e.g., "Electronics", "Office Supplies").
- Has a single field: `name`. Intentionally simple — it exists solely to organize products.
- Not a singleton. Multiple Category instances coexist. Each is a row in the database.
- Relationship: One Category can be associated with zero or more Products (one-to-many).

**Product (Model)**
- The core domain object. Represents a physical item in inventory.
- Tracks name, SKU, quantity, retail value, low-stock threshold, and timestamps.
- Contains business logic via the `is_low_stock` property, which compares current quantity against the threshold.
- Holds a ForeignKey reference to Category (nullable — products can be uncategorized).
- The `low_stock_notified` boolean flag implements a simple state machine: it flips to `True` when a low-stock email is sent, and resets to `False` when stock is replenished above the threshold. This prevents duplicate notifications.
- Not a singleton. Each Product instance represents one SKU in the inventory.

**ProductForm / CategoryForm (ModelForms)**
- Django ModelForm subclasses that bind HTML forms to their respective models.
- Handle input validation (required fields, data types, uniqueness constraints on SKU).
- Define Bootstrap-styled widgets for each field so the UI is consistent.
- These are instantiated per-request — a new form object is created each time a user loads a create/edit page. They are not singletons.

**ProductAdmin / CategoryAdmin (ModelAdmin)**
- Customize the Django admin interface for each model.
- Define which columns appear in list views, which fields are searchable/filterable.
- Registered via `@admin.register()` decorator — Django creates one instance per model registration (effectively singleton within the admin site).

**User (Django built-in)**
- We use Django's built-in `django.contrib.auth.User` model without modification.
- Handles authentication (login/logout), password hashing, and session management.
- Every view is protected with `@login_required`, which checks for an authenticated User in the session before allowing access.
- Currently all authenticated users see the same inventory (no per-user data isolation). This is a deliberate design choice for simplicity in this semester project.

### Modules (Non-Class Code)

**views.py — View Functions**
- We use **function-based views** (not class-based views). Each function handles one URL endpoint.
- Views are the controllers in Django's MTV (Model-Template-View) pattern. They:
  1. Receive an HTTP request
  2. Query/mutate models via the ORM
  3. Pass data to a template for rendering
  4. Return an HTTP response
- Views hold references to and use: Product, Category, ProductForm, CategoryForm, and `send_low_stock_email`.
- No view maintains state between requests — Django handles state via sessions and the database.

**utils.py — Email Notification Utility**
- Contains `send_low_stock_email(product)`, a standalone function (not a class method).
- Receives a Product instance, composes an alert email, sends it via Django's email backend (Gmail SMTP), and sets `product.low_stock_notified = True`.
- This function has a side effect: it mutates the Product object and calls `product.save()`.

**urls.py — URL Routing**
- Maps URL patterns to view functions. This is configuration, not logic.
- The project-level `urls.py` includes the app-level routes and adds auth routes (login/logout using Django's built-in `LoginView` and `LogoutView`).

### Control Flow and Threading

**Request-Response Model (No Threading)**
- InventoryIQ uses Django's standard synchronous request-response cycle. There is no multi-threading, async views, background workers, or task queues.
- Each HTTP request is handled by a single thread from start to finish: URL routing → view function → database queries → template rendering → HTTP response.
- Django's development server (`runserver`) is single-threaded. In production with Gunicorn, multiple worker processes handle concurrent requests, but each request is still handled synchronously within its process.

**External Communication**
- The only external communication is **outbound email via Gmail SMTP**. This happens synchronously within the `adjust_quantity` and `product_edit` view functions — the user's request blocks until the email is sent.
- This is a known limitation: if the SMTP server is slow or unreachable, the user experiences a delay. For a production system, this would be moved to a background task queue (e.g., Celery), but for this semester project, synchronous email is acceptable.
- There is no incoming webhook, API, WebSocket, or polling mechanism. The app is entirely request-driven.

**Database Access**
- All database access goes through Django's ORM (Object-Relational Mapper). No raw SQL is used.
- SQLite in development uses file-level locking. This is fine for single-user/low-traffic use but would not scale. The PostgreSQL configuration is ready in `settings.py` for production use.
- `select_related("category")` is used in list views and the finances page to avoid N+1 query problems (eager-loads the Category in a single JOIN query).

**Session and Authentication Control**
- Django's `SessionMiddleware` manages session state via cookies and server-side session storage.
- `AuthenticationMiddleware` attaches the current `User` object to every request.
- The `@login_required` decorator on every view function enforces authentication — unauthenticated requests are redirected to the login page.
- Login/logout are handled by Django's built-in `LoginView` and `LogoutView` class-based views (the only CBVs in the project).

### Intended Classes Not Yet Implemented

The following classes are planned for future iterations but are not yet in the codebase:

| Class | Purpose | Relationships |
|---|---|---|
| `Supplier` (Model) | Track product suppliers with contact info and lead times | One-to-many with Product (a supplier provides many products) |
| `PurchaseOrder` (Model) | Record orders placed to restock inventory | Many-to-one with Supplier; Many-to-many with Product (via line items) |
| `PurchaseOrderItem` (Model) | Line item linking a PurchaseOrder to a Product with quantity/price | Many-to-one with both PurchaseOrder and Product (association class) |
| `InventoryLog` (Model) | Audit trail of all quantity changes with timestamps and user | Many-to-one with Product and User |
| `UserProfile` (Model) | Extended user preferences (notification settings, role) | One-to-one with Django User |
