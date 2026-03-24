from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from .models import Product, Category
import csv
from .forms import ProductForm, CategoryForm


@login_required
def dashboard(request):
    """ Display inventory dashboard with key metrics and low stock alerts."""
    products = Product.objects.all()
    low_stock_products = [p for p in products if p.is_low_stock]
    context = {
        'total_products': products.count(),
        'low_stock_count': len(low_stock_products),
        'low_stock_products': low_stock_products,
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
def product_list(request):
    """
    Display all products with optional search and category filter,
    grouped by category with 'Not Under Category' always last.
    """
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')

    products = Product.objects.select_related('category').all().order_by('name')
    categories = Category.objects.all().order_by('name')

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    # Group products by category
    grouped_dict = {}

    for product in products:
        key = product.category.name if product.category else None
        if key not in grouped_dict:
            grouped_dict[key] = []
        grouped_dict[key].append(product)

    # Convert to ordered list
    grouped_products = []

    # Add categories first (sorted)
    for category in categories:
        if category.name in grouped_dict:
            grouped_products.append((category.name, grouped_dict[category.name]))

    # Add uncategorized LAST
    if None in grouped_dict:
        grouped_products.append(("Not Under Category", grouped_dict[None]))

    return render(request, 'inventory/product_list.html', {
        'grouped_products': grouped_products,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })


@login_required
def product_add(request):
    """Create a new product and optionally preselect its category."""
    category_id = request.GET.get('category')

    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully.')
            return redirect('product_list')
    else:
        if category_id:
            form = ProductForm(initial={'category': category_id})
        else:
            form = ProductForm()

    return render(request, 'inventory/product_form.html', {
        'form': form,
        'action': 'Add',
    })


@login_required
def product_edit(request, pk):
    """ Update an existing product indentified by its primary key (pk). """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully.')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'inventory/product_form.html', {'form': form, 'action': 'Edit'})


@login_required
def category_list(request):
    """ Display a list of all product categories. """
    categories = Category.objects.all().order_by('name')
    return render(request, 'inventory/category_list.html', {'categories': categories})


@login_required
def category_add(request):
    """ Create a new product category. """
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully.')
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'inventory/category_form.html', {'form': form, 'action': 'Add'})


@login_required
def category_detail(request, pk):
    """Display one category and all products assigned to it."""
    category = get_object_or_404(Category, pk=pk)
    products = Product.objects.filter(category=category).order_by('name')

    return render(request, 'inventory/category_detail.html', {
        'category': category,
        'products': products,
    })


@login_required
def adjust_quantity(request, pk):
    """Increase or decrease a product's quantity by 1."""
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        action = request.POST.get('action')
        if action == 'increment':
            product.quantity += 1
        elif action == 'decrement' and product.quantity > 0:
            # Prevent quantity from going below zero
            product.quantity -= 1
        product.save()
    return redirect('product_list')


@login_required
def export_csv(request):
    """Export all products as a CSV file for download."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Category', 'Quantity', 'Low Stock Threshold', 'Description'])
    for product in Product.objects.select_related('category').all():
        writer.writerow([
            product.name,
            product.category.name if product.category else '',
            product.quantity,
            product.low_stock_threshold,
            product.description,
        ])
    return response


@login_required
def product_delete(request, pk):
    """ Delete a product from the inventory after confirming the action. """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('product_list')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})
