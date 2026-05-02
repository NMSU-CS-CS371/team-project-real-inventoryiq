from django.contrib import admin
from .models import Product, Category, PurchaseOrder, PurchaseOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'quantity', 'low_stock_threshold', 'is_low_stock', 'updated_at']
    list_filter = ['category']
    search_fields = ['name']


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'supplier', 'status', 'created_at']
    list_filter = ['supplier', 'status']
    search_fields = ['order_number']
    inlines = [PurchaseOrderItemInline]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ['purchase_order', 'product', 'quantity']
    list_filter = ['purchase_order']
    search_fields = ['product__name']
