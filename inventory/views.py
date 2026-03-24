from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
from .models import Product, Category
from .forms import ProductForm


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
    Display all products with optional search and category filter.

    Query parameters:
    - q: Search term for product name, description, or category name.
    - category: Category ID to filter products by category.

    Returns:
    - Filtered list of products based on search input and category selection.
    """

    # Get search Inputs from URL
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    
    # Base queryset
    products = Product.objects.select_related('category').all()
    categories = Category.objects.all()

    # Apply search filtering if search query exists
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    # Apply category filtering if category_id is provided
    if category_id:
        products = products.filter(category_id=category_id)

    # Send data to template
    return render(request, 'inventory/product_list.html', {
        'products': products,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })


@login_required
def product_add(request):
    """ Create a new product and save it to the inventory. """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully.')
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'inventory/product_form.html', {'form': form, 'action': 'Add'})


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
