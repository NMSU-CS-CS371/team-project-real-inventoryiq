import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, ProductForm, ExpenseForm
from .models import Category, Product, Expense
from .utils import send_low_stock_email


@login_required
def dashboard(request):
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
        'activity_items': all_products[:5],
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
def product_list(request):
    """
    Display products with optional search/filter, grouped by category.

    Categories are shown alphabetically.
    Products without a category are grouped under 'Not Under Category' last.
    """

    # Read search/filter values from the URL
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()

    # Base product/category queries
    products = Product.objects.select_related("category").all().order_by("name")
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

    # Temporary dictionary for grouping products
    grouped_dict = {}

    for product in products:
        key = product.category.name if product.category else None
        if key not in grouped_dict:
            grouped_dict[key] = []
        grouped_dict[key].append(product)

    # Final ordered grouping for display
    grouped_products = []

    # Add categories first in alphabetical order
    for category in categories:
        if category.name in grouped_dict:
            grouped_products.append((category.name, grouped_dict[category.name]))

    # Add uncategorized products last
    if None in grouped_dict:
        grouped_products.append(("Not Under Category", grouped_dict[None]))

    return render(
        request,
        "inventory/product_list.html",
        {
            "grouped_products": grouped_products,
            "categories": categories,
            "query": query,
            "selected_category": category_id,
        },
    )


@login_required
def product_add(request):
    """Create a new product and optionally preselect its category."""

    # Allows category to be preselected when coming from a category page
    category_id = request.GET.get("category")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
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
    """Update an existing product."""

    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            updated_product = form.save()
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
    """Delete a product from the inventory after confirming the action."""

    product = get_object_or_404(Product, pk=pk)
    category_pk = product.category.pk if product.category else None

    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")

        # Redirect to the category page if the product had a category
        if category_pk:
            return redirect("category_detail", pk=category_pk)
        return redirect("product_list")

    return render(
        request, "inventory/product_confirm_delete.html", {"product": product}
    )


@login_required
def category_list(request):
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('name')
    return render(request, 'inventory/category_list.html', {'categories': parent_categories})


@login_required
def category_add(request):
    """Create a new product category."""

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
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
    category = get_object_or_404(Category, pk=pk)
    subcategories = category.subcategories.all().order_by('name')
    products = Product.objects.filter(category=category).order_by('name')

    selected_subcategory = request.GET.get('subcategory', '').strip()
    if selected_subcategory:
        products = Product.objects.filter(category_id=selected_subcategory).order_by('name')

    return render(request, 'inventory/category_detail.html', {
        'category': category,
        'products': products,
        'subcategories': subcategories,
        'selected_subcategory': selected_subcategory,
    })


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully.')
        return redirect('category_list')

    return render(request, 'inventory/category_confirm_delete.html', {
        'category': category,
    })


@login_required
def adjust_quantity(request, pk):
    """Increase or decrease a product quantity by 1."""

    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "increment":
            product.quantity += 1
        elif action == "decrement" and product.quantity > 0:
            # Prevent quantity from going below zero
            product.quantity -= 1

        product.save()

        # Send email if stock just dropped low (and we haven't already notified)
        if product.is_low_stock and not product.low_stock_notified:
            send_low_stock_email(product)

        # Reset the flag if stock is back above the threshold
        if not product.is_low_stock and product.low_stock_notified:
            product.low_stock_notified = False
            product.save()

    # Return to category page if applicable
    if product.category:
        return redirect("category_detail", pk=product.category.pk)
    return redirect("product_list")


@login_required
def finances(request):
    """Display the total retail value of all inventory stock."""
    if request.method == "POST":
        expense_form = ExpenseForm(request.POST)
        if expense_form.is_valid():
            expense_form.save()
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
def export_csv(request):
    """Export all products as a CSV file for download."""

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
