from django import forms
from .models import Product, Category

class ProductForm(forms.ModelForm):
    """Form used to create and update products in the inventory system."""
    class Meta:
        model = Product
        fields = ['name', 'category', 'quantity', 'low_stock_threshold', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
        }


class CategoryForm(forms.ModelForm):
    """Form used to create product categories."""
    class Meta:
        model = Category
        fields = ['name', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
        }