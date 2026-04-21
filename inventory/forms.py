from django import forms

from .models import Category, Product, Expense


class ProductForm(forms.ModelForm):
    """Form used to create and update products in the inventory system."""

    class Meta:
        model = Product
        fields = [
            "name",
            "sku_number",
            "retail_value",
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
