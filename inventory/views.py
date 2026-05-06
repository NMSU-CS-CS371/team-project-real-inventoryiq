import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
def product_list(request):
    # shows all the products, organized by category. you can search and filter too
    # grabs search/filter values from the URL
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()

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
        products_in_group = grouped_dict.get(category.id)
        if products_in_group:
            grouped_products.append(
                {
                    "name": category.name,
                    "category": category,
                    "products": products_in_group,
                    "collapse_id": f"category-products-{category.id}",
                }
            )

    if None in grouped_dict:
        grouped_products.append(
            {
                "name": "Not Under Category",
                "category": None,
                "products": grouped_dict[None],
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
