from django.contrib import admin
from .models import ActivityLog, Product, Category, PurchaseOrder, PurchaseOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # shows the category name in the admin list view
    list_display = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # shows product details in the admin list, lets you filter by category and search by name
    list_display = ['name', 'category', 'quantity', 'display_order', 'low_stock_threshold', 'is_low_stock', 'updated_at']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['message', 'activity_type', 'created_at']
    list_filter = ['activity_type']
    search_fields = ['message']


class PurchaseOrderItemInline(admin.TabularInline):
    # lets you add/edit purchase order items inline while editing a purchase order
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    # shows purchase order details, lets you filter by supplier/status, and edit items inline
    list_display = ['order_number', 'supplier', 'status', 'created_at']
    list_filter = ['supplier', 'status']
    search_fields = ['order_number']
    inlines = [PurchaseOrderItemInline]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    # shows individual purchase order items and lets you filter/search by order and product
    list_display = ['purchase_order', 'product', 'quantity']
    list_filter = ['purchase_order']
    search_fields = ['product__name']
