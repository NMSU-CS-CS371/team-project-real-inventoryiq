from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count
from .models import Product, Category
import csv
from .forms import ProductForm, CategoryForm


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

    category_breakdown = Category.objects.annotate(product_count=Count('product')).order_by('name')

    context = {
        'total_products': len(all_products),
        'low_stock_count': len(low_stock_products),
        'total_categories': Category.objects.count(),
        'inventory_value': '—',
        'recent_products': filtered_products[:8],
        'critical_products': critical_products[:5],
        'category_breakdown': category_breakdown,
        'categories': categories,
        'query': query,
        'selected_status': status_filter,
        'selected_category': category_filter,
        'activity_items' : all_products[:5],
    }

    return render(request, 'inventory/dashboard.html', context)


@login_required
def product_list(request):
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

    grouped_dict = {}

    for product in products:
        key = product.category.name if product.category else None
        if key not in grouped_dict:
            grouped_dict[key] = []
        grouped_dict[key].append(product)

    grouped_products = []

    for category in categories:
        if category.name in grouped_dict:
            grouped_products.append((category.name, grouped_dict[category.name]))

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
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('name')
    return render(request, 'inventory/category_list.html', {'categories': parent_categories})


@login_required
def category_add(request):
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
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        action = request.POST.get('action')
        if action == 'increment':
            product.quantity += 1
        elif action == 'decrement' and product.quantity > 0:
            product.quantity -= 1
        product.save()
    return redirect('product_list')


@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=\"inventory.csv\"'
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
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('product_list')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})