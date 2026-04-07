import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, ProductForm
from .models import Category, Product
from .utils import send_low_stock_email


@login_required
def dashboard(request):
    """Display inventory dashboard with key metrics and low stock alerts."""

    # Calculate total products and identify low stock items
    products = Product.objects.all()
    low_stock_products = [p for p in products if p.is_low_stock]

    # Data sent to the dashboard template
    context = {
        "total_products": products.count(),
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products,
    }
    return render(request, "inventory/dashboard.html", context)


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
    """Display a list of all product categories."""

    categories = Category.objects.all().order_by("name")
    return render(request, "inventory/category_list.html", {"categories": categories})


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
    """Display one category and all products assigned to it."""

    category = get_object_or_404(Category, pk=pk)
    products = Product.objects.filter(category=category).order_by("name")

    return render(
        request,
        "inventory/category_detail.html",
        {
            "category": category,
            "products": products,
        },
    )


@login_required
def category_detail(request, pk):
    """Display one category and all products assigned to it."""
    category = get_object_or_404(Category, pk=pk)
    products = Product.objects.filter(category=category).order_by("name")

    return render(
        request,
        "inventory/category_detail.html",
        {
            "category": category,
            "products": products,
        },
    )


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
