import csv
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CategoryForm, ProductForm, ExpenseForm, PurchaseOrderForm, PurchaseOrderItemFormSet
from .models import ActivityLog, Category, Product, Expense, PurchaseOrder
from .utils import log_activity, send_low_stock_email


def _next_product_order(category_id):
    max_order = (
        Product.objects.filter(category_id=category_id)
        .aggregate(Max("display_order"))
        .get("display_order__max")
    )
    if max_order is None:
        return 0
    return max_order + 1


def _category_label(category):
    return category.name if category else "Uncategorized"


def _product_search_url(product, query):
    params = {
        "q": query or product.name,
        "highlight_product": product.id,
    }
    return f"{reverse('product_list')}?{urlencode(params)}"


def _page_search_results(query):
    pages = [
        {
            "title": "Dashboard",
            "subtitle": "Overview, activity, and inventory health",
            "url": reverse("dashboard"),
            "keywords": "dashboard home overview activity analytics inventory health",
        },
        {
            "title": "Products",
            "subtitle": "Inventory, stock, SKUs, and categories",
            "url": reverse("product_list"),
            "keywords": "products product inventory stock sku items",
        },
        {
            "title": "Categories",
            "subtitle": "Product groups and subcategories",
            "url": reverse("category_list"),
            "keywords": "categories category groups organization",
        },
        {
            "title": "Purchase Orders",
            "subtitle": "Supplier orders and incoming stock",
            "url": reverse("purchase_order_list"),
            "keywords": "purchase orders order supplier incoming stock",
        },
        {
            "title": "Finances",
            "subtitle": "Expenses, value, costs, and profit",
            "url": reverse("finances"),
            "keywords": "finance finances financial expense expenses money value cost costs profit",
        },
    ]
    if not query:
        return []

    query_lower = query.lower()
    return [
        page
        for page in pages
        if query_lower in page["title"].lower() or query_lower in page["keywords"]
    ]


@login_required
def dashboard(request):
    # grabs all the search and filter stuff from the URL so we can use it
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    category_filter = request.GET.get('category', '').strip()

    products = Product.objects.select_related('category').all().order_by('-updated_at')
    categories = Category.objects.all().order_by('name')

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    if category_filter:
        products = products.filter(category_id=category_filter)

    filtered_products = list(products)

    if status_filter == 'critical':
        filtered_products = [p for p in filtered_products if p.quantity <= 2]
    elif status_filter == 'low':
        filtered_products = [p for p in filtered_products if p.is_low_stock and p.quantity > 2]
    elif status_filter == 'healthy':
        filtered_products = [p for p in filtered_products if not p.is_low_stock]

    all_products = list(Product.objects.select_related('category').all())
    low_stock_products = [p for p in all_products if p.is_low_stock]
    critical_products = [p for p in all_products if p.quantity <= 2]
    category_nodes = {
        category.id: {"name": category.name, "parent_id": category.parent_id}
        for category in Category.objects.all()
    }
    finance_category_map = {}
    expenses = list(Expense.objects.all())
    expenses_total = sum((expense.amount for expense in expenses), Decimal("0.00"))
    grand_total = Decimal("0.00")

    for product in all_products:
        retail = product.retail_value or Decimal("0.00")
        cost = product.cost_value or Decimal("0.00")
        line_total_sell = retail * product.quantity
        line_total_buy = cost * product.quantity
        line_total_profit = line_total_sell - line_total_buy
        grand_total += line_total_sell

        if product.category_id:
            top_level_id = product.category_id
            visited = set()
            while True:
                node = category_nodes.get(top_level_id)
                if not node:
                    break
                parent_id = node["parent_id"]
                if not parent_id or parent_id in visited:
                    break
                visited.add(top_level_id)
                top_level_id = parent_id

            top_level_name = category_nodes.get(top_level_id, {}).get(
                "name",
                product.category.name,
            )
            bucket_key = f"category-{top_level_id}"
        else:
            top_level_name = "Uncategorized"
            bucket_key = "uncategorized"

        bucket = finance_category_map.setdefault(
            bucket_key,
            {
                "category_name": top_level_name,
                "product_count": 0,
                "category_total_cost": Decimal("0.00"),
                "category_total_buy": Decimal("0.00"),
                "category_total_sell": Decimal("0.00"),
                "category_total_profit": Decimal("0.00"),
            },
        )
        bucket["product_count"] += 1
        # Keep this existing key as the inventory total used in the dashboard table/chart.
        bucket["category_total_cost"] += line_total_sell
        bucket["category_total_buy"] += line_total_buy
        bucket["category_total_sell"] += line_total_sell
        bucket["category_total_profit"] += line_total_profit

    finance_category_breakdown = sorted(
        [row for key, row in finance_category_map.items() if key != "uncategorized"],
        key=lambda row: row["category_name"].lower(),
    )
    uncategorized_row = finance_category_map.get("uncategorized")
    if uncategorized_row:
        finance_category_breakdown.append(uncategorized_row)

    inventory_chart_labels = []
    inventory_chart_values = []
    for row in finance_category_breakdown:
        total_value = float(row["category_total_cost"])
        if total_value > 0:
            inventory_chart_labels.append(row["category_name"])
            inventory_chart_values.append(total_value)

    # Keep these existing keys for compatibility.
    finance_chart_labels = list(inventory_chart_labels)
    finance_chart_values = list(inventory_chart_values)
    finance_chart_labels.append("Expenses")
    finance_chart_values.append(float(expenses_total))

    finance_position_labels = ["Total Expenses"]
    finance_position_expense_values = [float(expenses_total)]
    finance_position_buy_values = [0.0]
    finance_position_sell_values = [0.0]
    finance_position_profit_values = [0.0]

    for row in finance_category_breakdown:
        finance_position_labels.append(row["category_name"])
        finance_position_expense_values.append(0.0)
        finance_position_buy_values.append(float(row["category_total_buy"]))
        finance_position_sell_values.append(float(row["category_total_sell"]))
        finance_position_profit_values.append(float(row["category_total_profit"]))

    finance_position_breakdown = sorted(
        finance_category_breakdown,
        key=lambda row: (-row["category_total_sell"], row["category_name"].lower()),
    )

    net_inventory_value = grand_total - expenses_total

    category_breakdown = Category.objects.annotate(product_count=Count('product')).order_by('name')
    activity_cutoff = timezone.now() - timedelta(days=7)
    activity_items = ActivityLog.objects.filter(created_at__gte=activity_cutoff)[:30]

    context = {
        'total_products': len(all_products),
        'low_stock_count': len(low_stock_products),
        'total_categories': Category.objects.count(),
        'inventory_value': f"${grand_total:,.2f}",
        'recent_products': filtered_products[:8],
        'critical_products': critical_products[:5],
        'category_breakdown': category_breakdown,
        'categories': categories,
        'query': query,
        'selected_status': status_filter,
        'selected_category': category_filter,
        'activity_items': activity_items,
        'recent_expenses': expenses[:8],
        'finance_category_breakdown': finance_category_breakdown,
        'grand_total': grand_total,
        'expenses_total': expenses_total,
        'net_inventory_value': net_inventory_value,
        'finance_chart_labels': finance_chart_labels,
        'finance_chart_values': finance_chart_values,
        'inventory_chart_labels': inventory_chart_labels,
        'inventory_chart_values': inventory_chart_values,
        'finance_position_labels': finance_position_labels,
        'finance_position_expense_values': finance_position_expense_values,
        'finance_position_buy_values': finance_position_buy_values,
        'finance_position_sell_values': finance_position_sell_values,
        'finance_position_profit_values': finance_position_profit_values,
        'finance_position_breakdown': finance_position_breakdown,
    }

    return render(request, 'inventory/dashboard.html', context)


@login_required
def global_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []

    if len(query) >= 2:
        for page in _page_search_results(query)[:3]:
            results.append(
                {
                    "type": "Page",
                    "title": page["title"],
                    "subtitle": page["subtitle"],
                    "url": page["url"],
                }
            )

        products = (
            Product.objects.select_related("category")
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(sku_number__icontains=query)
                | Q(category__name__icontains=query)
            )
            .order_by("name")[:5]
        )
        for product in products:
            sku = f" • SKU {product.sku_number}" if product.sku_number else ""
            results.append(
                {
                    "type": "Product",
                    "title": product.name,
                    "subtitle": f"{_category_label(product.category)} • Qty {product.quantity}{sku}",
                    "url": _product_search_url(product, query),
                }
            )

        categories = Category.objects.filter(
            Q(name__icontains=query) | Q(parent__name__icontains=query)
        ).order_by("name")[:3]
        for category in categories:
            results.append(
                {
                    "type": "Category",
                    "title": category.name,
                    "subtitle": "Open category",
                    "url": reverse("category_detail", args=[category.pk]),
                }
            )

        orders = PurchaseOrder.objects.filter(
            Q(order_number__icontains=query)
            | Q(supplier__icontains=query)
            | Q(note__icontains=query)
        ).order_by("-created_at")[:3]
        for order in orders:
            results.append(
                {
                    "type": "Order",
                    "title": order.order_number,
                    "subtitle": f"{order.get_supplier_display()} • {order.get_status_display()}",
                    "url": reverse("purchase_order_edit", args=[order.pk]),
                }
            )

        expenses = Expense.objects.filter(note__icontains=query).order_by("-date", "-created_at")[:3]
        for expense in expenses:
            results.append(
                {
                    "type": "Expense",
                    "title": expense.note or f"Expense ${expense.amount}",
                    "subtitle": f"${expense.amount} • {expense.date:%b %d, %Y}",
                    "url": reverse("finances"),
                }
            )

    return JsonResponse({"results": results[:10]})


@login_required
def global_search(request):
    query = request.GET.get("q", "").strip()

    page_results = _page_search_results(query)
    product_results = Product.objects.none()
    category_results = Category.objects.none()
    order_results = PurchaseOrder.objects.none()
    expense_results = Expense.objects.none()

    if query:
        product_results = (
            Product.objects.select_related("category")
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(sku_number__icontains=query)
                | Q(category__name__icontains=query)
            )
            .order_by("name")
        )
        category_results = Category.objects.filter(
            Q(name__icontains=query) | Q(parent__name__icontains=query)
        ).order_by("name")
        order_results = PurchaseOrder.objects.filter(
            Q(order_number__icontains=query)
            | Q(supplier__icontains=query)
            | Q(note__icontains=query)
        ).order_by("-created_at")
        expense_results = Expense.objects.filter(note__icontains=query).order_by(
            "-date", "-created_at"
        )

    return render(
        request,
        "inventory/search_results.html",
        {
            "query": query,
            "page_results": page_results,
            "product_results": product_results,
            "category_results": category_results,
            "order_results": order_results,
            "expense_results": expense_results,
        },
    )


@login_required
def product_list(request):
    # shows all the products, organized by category. you can search and filter too
    # grabs search/filter values from the URL
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    highlight_product = request.GET.get("highlight_product", "").strip()

    # Base product/category queries
    products = Product.objects.select_related("category").all().order_by("display_order", "name")
    categories = Category.objects.all().order_by("name")

    # Search by product name, description, or category name
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    # Filter by selected category if provided
    if category_id:
        products = products.filter(category_id=category_id)

    grouped_dict = {}
    for product in products:
        grouped_dict.setdefault(product.category_id, []).append(product)

    grouped_products = []
    for category in categories:
        products_in_group = grouped_dict.get(category.id, [])
        grouped_products.append(
            {
                "name": category.name,
                "category": category,
                "category_id": str(category.id),
                "products": products_in_group,
                "collapse_id": f"category-products-{category.id}",
            }
        )

    grouped_products.append(
        {
            "name": "Not Under Category",
            "category": None,
            "category_id": "",
            "products": grouped_dict.get(None, []),
            "collapse_id": "category-products-uncategorized",
        }
    )

    return render(
        request,
        "inventory/product_list.html",
        {
            "grouped_products": grouped_products,
            "categories": categories,
            "query": query,
            "selected_category": category_id,
            "highlight_product": highlight_product,
            "total_visible_products": sum(
                len(group["products"]) for group in grouped_products
            ),
        },
    )


@login_required
def product_add(request):
    # creates a new product. can pre-select the category if you come from the category page
    category_id = request.GET.get("category")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.display_order = _next_product_order(product.category_id)
            product.save()
            log_activity("product", f"Added product: {product.name}.")
            messages.success(request, "Product added successfully.")

            # Redirect back to that category if product belongs to one
            if product.category:
                return redirect("category_detail", pk=product.category.pk)
            return redirect("product_list")
    else:
        # Prefill category field if category was passed in URL
        if category_id:
            form = ProductForm(initial={"category": category_id})
        else:
            form = ProductForm()

    return render(
        request,
        "inventory/product_form.html",
        {
            "form": form,
            "action": "Add",
        },
    )


@login_required
def product_edit(request, pk):
    # lets you edit a product that already exists
    product = get_object_or_404(Product, pk=pk)
    original_category_id = product.category_id

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            updated_product = form.save(commit=False)
            if updated_product.category_id != original_category_id:
                updated_product.display_order = _next_product_order(updated_product.category_id)
            updated_product.save()
            log_activity("product", f"Updated product: {updated_product.name}.")
            messages.success(request, "Product updated successfully.")

            # Check low stock after manual edit
            if updated_product.is_low_stock and not updated_product.low_stock_notified:
                send_low_stock_email(updated_product)
            if not updated_product.is_low_stock and updated_product.low_stock_notified:
                updated_product.low_stock_notified = False
                updated_product.save()

            # Return to the category page if the product has a category
            if updated_product.category:
                return redirect("category_detail", pk=updated_product.category.pk)
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "inventory/product_form.html",
        {
            "form": form,
            "action": "Edit",
        },
    )


@login_required
def product_delete(request, pk):
    # deletes a product but asks you to confirm first so you don't mess up
    product = get_object_or_404(Product, pk=pk)
    category_pk = product.category.pk if product.category else None
    product_name = product.name

    if request.method == "POST":
        product.delete()
        log_activity("product", f"Removed product: {product_name}.")
        messages.success(request, "Product deleted.")

        # Redirect to the category page if the product had a category
        if category_pk:
            return redirect("category_detail", pk=category_pk)
        return redirect("product_list")

    return render(
        request, "inventory/product_confirm_delete.html", {"product": product}
    )


@login_required
@require_POST
def product_reorder(request):
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

        groups = payload.get("groups")
        if not isinstance(groups, list) or not groups:
            return JsonResponse({"success": False, "error": "No product groups to save."}, status=400)

        category_ids = set()
        parsed_groups = []
        product_ids = []
        seen_product_ids = set()

        for group in groups:
            if not isinstance(group, dict):
                return JsonResponse({"success": False, "error": "Invalid product group."}, status=400)

            raw_category_id = group.get("category_id")
            if raw_category_id in (None, "", "null", "uncategorized"):
                category_id = None
            else:
                try:
                    category_id = int(raw_category_id)
                except (TypeError, ValueError):
                    return JsonResponse({"success": False, "error": "Invalid category."}, status=400)
                category_ids.add(category_id)

            raw_product_ids = group.get("product_ids", [])
            if not isinstance(raw_product_ids, list):
                return JsonResponse({"success": False, "error": "Invalid product order."}, status=400)

            parsed_product_ids = []
            for raw_product_id in raw_product_ids:
                try:
                    product_id = int(raw_product_id)
                except (TypeError, ValueError):
                    return JsonResponse({"success": False, "error": "Invalid product."}, status=400)
                if product_id in seen_product_ids:
                    return JsonResponse({"success": False, "error": "Product listed twice."}, status=400)
                seen_product_ids.add(product_id)
                product_ids.append(product_id)
                parsed_product_ids.append(product_id)

            parsed_groups.append((category_id, parsed_product_ids))

        valid_category_ids = set(
            Category.objects.filter(id__in=category_ids).values_list("id", flat=True)
        )
        if valid_category_ids != category_ids:
            return JsonResponse({"success": False, "error": "Category not found."}, status=400)

        if not product_ids:
            return JsonResponse({"success": True})

        products_by_id = Product.objects.select_related("category").in_bulk(product_ids)
        if len(products_by_id) != len(set(product_ids)):
            return JsonResponse({"success": False, "error": "Product not found."}, status=400)

        old_category_ids = {
            product_id: product.category_id for product_id, product in products_by_id.items()
        }
        old_display_orders = {
            product_id: product.display_order for product_id, product in products_by_id.items()
        }
        label_category_ids = {
            category_id for category_id, _ in parsed_groups if category_id
        } | {
            category_id for category_id in old_category_ids.values() if category_id
        }
        category_names = {
            category.id: category.name
            for category in Category.objects.filter(id__in=label_category_ids)
        }

        moved_messages = []
        reordered_categories = set()
        for category_id, group_product_ids in parsed_groups:
            for display_order, product_id in enumerate(group_product_ids):
                product = products_by_id[product_id]
                old_category_id = old_category_ids[product_id]
                old_display_order = old_display_orders[product_id]

                product.category_id = category_id
                product.display_order = display_order

                if old_category_id != category_id:
                    old_name = category_names.get(old_category_id, "Uncategorized")
                    new_name = category_names.get(category_id, "Uncategorized")
                    moved_messages.append(
                        f"Moved {product.name} from {old_name} to {new_name}."
                    )
                elif old_display_order != display_order:
                    reordered_categories.add(category_names.get(category_id, "Uncategorized"))

        Product.objects.bulk_update(products_by_id.values(), ["category", "display_order"])

        for message in moved_messages:
            log_activity("product", message)
        if not moved_messages:
            for category_name in sorted(reordered_categories):
                log_activity("product", f"Reordered products in {category_name}.")

        return JsonResponse({"success": True})

    order_value = request.POST.get("product_order", "")
    try:
        product_ids = [int(value) for value in order_value.split(",") if value.strip()]
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid product order."}, status=400)

    if not product_ids:
        return JsonResponse({"success": False, "error": "No products to reorder."}, status=400)

    products = list(Product.objects.select_related("category").filter(id__in=product_ids))
    if len(products) != len(product_ids):
        return JsonResponse({"success": False, "error": "Product list changed."}, status=400)

    category_ids = {product.category_id for product in products}
    if len(category_ids) != 1:
        return JsonResponse({"success": False, "error": "Products must stay in one category."}, status=400)

    product_by_id = {product.id: product for product in products}
    for display_order, product_id in enumerate(product_ids):
        product_by_id[product_id].display_order = display_order

    Product.objects.bulk_update(product_by_id.values(), ["display_order"])

    first_product = products[0]
    category_name = first_product.category.name if first_product.category else "Not Under Category"
    log_activity("product", f"Reordered products in {category_name}.")

    return JsonResponse({"success": True})


@login_required
def category_list(request):
    # shows all the top-level categories and their subcategories
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('name')
    return render(request, 'inventory/category_list.html', {'categories': parent_categories})


@login_required
def category_add(request):
    # creates a new category to organize products
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            log_activity("category", f"Added category: {category.name}.")
            messages.success(request, "Category added successfully.")
            return redirect("category_detail", pk=category.pk)
    else:
        form = CategoryForm()
    return render(
        request,
        "inventory/category_form.html",
        {
            "form": form,
            "action": "Add",
        },
    )


@login_required
def category_detail(request, pk):
    # shows all the products in a specific category and its subcategories
    category = get_object_or_404(Category, pk=pk)
    subcategories = category.subcategories.all().order_by('name')
    products = Product.objects.filter(category=category).order_by('display_order', 'name')

    selected_subcategory = request.GET.get('subcategory', '').strip()
    if selected_subcategory:
        products = Product.objects.filter(category_id=selected_subcategory).order_by('display_order', 'name')

    return render(request, 'inventory/category_detail.html', {
        'category': category,
        'products': products,
        'subcategories': subcategories,
        'selected_subcategory': selected_subcategory,
    })


@login_required
def category_delete(request, pk):
    # deletes a category after you confirm
    category = get_object_or_404(Category, pk=pk)
    category_name = category.name

    if request.method == 'POST':
        category.delete()
        log_activity("category", f"Removed category: {category_name}.")
        messages.success(request, 'Category deleted successfully.')
        return redirect('category_list')

    return render(request, 'inventory/category_confirm_delete.html', {
        'category': category,
    })


@login_required
def adjust_quantity(request, pk):
    # adds or removes 1 item from the product's quantity (like a quick adjust button)
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")
        old_quantity = product.quantity
        changed = False

        if action == "increment":
            product.quantity += 1
            changed = True
        elif action == "decrement" and product.quantity > 0:
            # Prevent quantity from going below zero
            product.quantity -= 1
            changed = True

        if changed:
            product.save()
            log_activity(
                "stock",
                f"Adjusted stock for {product.name}: {old_quantity} to {product.quantity}.",
            )

            # Send email if stock just dropped low (and we haven't already notified)
            if product.is_low_stock and not product.low_stock_notified:
                send_low_stock_email(product)

            # Reset the flag if stock is back above the threshold
            if not product.is_low_stock and product.low_stock_notified:
                product.low_stock_notified = False
                product.save()

    # Return to category page if applicable
    #if product.category:
    #    return redirect("category_detail", pk=product.category.pk)
    return redirect("product_list")


@login_required
def finances(request):
    # shows the money stuff - like how much the inventory is worth, profits, expenses, etc
    if request.method == "POST":
        expense_form = ExpenseForm(request.POST)
        if expense_form.is_valid():
            expense = expense_form.save()
            log_activity("expense", f"Recorded expense: ${expense.amount}.")
            messages.success(request, "Expense added.")
            return redirect("finances")
    else:
        expense_form = ExpenseForm()

    products = Product.objects.select_related("category").all().order_by("name")
    expenses = list(Expense.objects.all())

    product_data = []
    grand_total = 0
    total_cost = 0
    potential_profit = 0

    for product in products:
        retail = product.retail_value or 0
        cost = product.cost_value or 0
        line_total = retail * product.quantity
        line_cost = cost * product.quantity
        line_profit = (retail - cost) * product.quantity
        grand_total += line_total
        total_cost += line_cost
        potential_profit += line_profit
        product_data.append(
            {
                "name": product.name,
                "category": product.category,
                "retail_value": retail,
                "cost_value": cost,
                "quantity": product.quantity,
                "line_total": line_total,
                "line_profit": line_profit,
            }
        )

    expenses_total = sum((expense.amount for expense in expenses), Decimal("0.00"))
    net_inventory_value = grand_total - expenses_total

    context = {
        "product_data": product_data,
        "grand_total": grand_total,
        "total_cost": total_cost,
        "potential_profit": potential_profit,
        "expenses": expenses,
        "expenses_total": expenses_total,
        "net_inventory_value": net_inventory_value,
        "expense_form": expense_form,
    }
    return render(request, "inventory/finances.html", context)


@login_required
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    amount = expense.amount
    expense.delete()
    log_activity("expense", f"Removed expense: ${amount}.")
    messages.success(request, "Expense removed.")
    return redirect("finances")


@login_required
def export_csv(request):
    # lets you download all the products as a CSV file so you can use it in excel or wherever
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="inventory.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Name",
            "SKU Number",
            "Category",
            "Quantity",
            "Low Stock Threshold",
            "Description",
        ]
    )

    for product in (
        Product.objects.select_related("category")
        .all()
        .order_by("category__name", "name")
    ):
        writer.writerow(
            [
                product.name,
                product.sku_number,
                product.category.name if product.category else "Not Under Category",
                product.quantity,
                product.low_stock_threshold,
                product.description,
            ]
        )
    return response


@login_required
def purchase_order_list(request):
    # shows all the purchase orders you've created
    orders = PurchaseOrder.objects.prefetch_related('items').all()
    return render(request, 'inventory/purchase_order_list.html', {'orders': orders})


@login_required
def purchase_order_create(request):
    # creates a new purchase order for ordering stuff from suppliers
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            order = form.save()
            formset.instance = order
            formset.save()
            log_activity("purchase_order", f"Created purchase order: {order.order_number}.")
            messages.success(request, 'Purchase order created.')
            return redirect('purchase_order_list')
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()
    return render(request, 'inventory/purchase_order_form.html', {
        'form': form, 'formset': formset, 'action': 'New'
    })


@login_required
def purchase_order_edit(request, pk):
    # edits an existing purchase order
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = PurchaseOrderItemFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            order = form.save()
            formset.save()
            log_activity("purchase_order", f"Updated purchase order: {order.order_number}.")
            messages.success(request, 'Purchase order updated.')
            return redirect('purchase_order_list')
    else:
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderItemFormSet(instance=order)
    return render(request, 'inventory/purchase_order_form.html', {
        'form': form, 'formset': formset, 'action': 'Edit', 'order': order
    })


@login_required
def purchase_order_delete(request, pk):
    # deletes a purchase order after you confirm
    order = get_object_or_404(PurchaseOrder, pk=pk)
    order_number = order.order_number
    if request.method == 'POST':
        order.delete()
        log_activity("purchase_order", f"Removed purchase order: {order_number}.")
        messages.success(request, 'Purchase order deleted.')
        return redirect('purchase_order_list')
    return render(request, 'inventory/purchase_order_confirm_delete.html', {'order': order})


@login_required
def purchase_order_receive(request, pk):
    if request.method == 'POST':
        order = get_object_or_404(PurchaseOrder, pk=pk, status='pending')
        for item in order.items.all():
            item.product.quantity += item.quantity
            item.product.save()
        order.status = 'received'
        order.save()
        log_activity("purchase_order", f"Received purchase order: {order.order_number}.")
        messages.success(request, f'Purchase order {order.order_number} marked as received. Stock updated.')
    return redirect('purchase_order_list')
