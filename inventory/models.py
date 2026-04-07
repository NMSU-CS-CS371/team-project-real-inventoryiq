from django.db import models


class Category(models.Model):
    """Represents a product category used for organizing and filtering products in the inventory."""

    name = models.CharField(max_length=100)

    def __str__(self):
        """Return the category name for display purposes."""
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Product(models.Model):
    """Represents a product in the inventory."""

    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sku_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    low_stock_notified = models.BooleanField(default=False)
    retail_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        """Return the product name for display purposes."""
        return self.name

    @property
    def is_low_stock(self):
        """Return True if the product quantity is at or below the low stock threshold."""
        return self.quantity <= self.low_stock_threshold
