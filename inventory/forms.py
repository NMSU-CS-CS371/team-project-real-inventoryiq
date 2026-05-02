from django import forms
from django.forms import inlineformset_factory

from .models import Category, Product, Expense, PurchaseOrder, PurchaseOrderItem


class ProductForm(forms.ModelForm):
    """Form used to create and update products in the inventory system."""

    class Meta:
        model = Product
        fields = [
            "name",
            "sku_number",
            "retail_value",
            "cost_value",
            "category",
            "quantity",
            "low_stock_threshold",
            "description",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Product name"}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "low_stock_threshold": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional description",
                }
            ),
            "sku_number": forms.TextInput(attrs={"class": "form-control"}),
            "retail_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "cost_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }


class CategoryForm(forms.ModelForm):
    """Form used to create product categories."""

    class Meta:
        model = Category
        fields = ["name", "parent"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Category name"}
            ),
            "parent": forms.Select(attrs={"class": "form-select"}),
        }


class ExpenseForm(forms.ModelForm):
    """Simple form for adding expenses from the finance page."""

    class Meta:
        model = Expense
        fields = ["amount", "date", "note"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0.00"}
            ),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional note"}),
        }


class PurchaseOrderForm(forms.ModelForm):
    """Order-level fields for creating and editing a purchase order."""

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'order_number', 'note', 'delivery_date']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. PO-2026-001'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter a note for this order (optional)'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }


class PurchaseOrderItemForm(forms.ModelForm):
    """Single line-item row within a purchase order formset."""

    class Meta:
        model = PurchaseOrderItem
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1'}),
        }


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
    max_num=50,
    validate_max=True,
)
