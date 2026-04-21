from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Represents a product category used for organizing and filtering products in the inventory."""

    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]


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
    cost_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        """Return the product name for display purposes."""
        return self.name

    @property
    def is_low_stock(self):
        """Return True if the product quantity is at or below the low stock threshold."""
        return self.quantity <= self.low_stock_threshold


class Expense(models.Model):
    """Simple expense record used by the finance page and dashboard rollups."""

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Expense ${self.amount} on {self.date}"


class DebtAccount(models.Model):
    name = models.CharField(max_length=150)
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    apr = models.DecimalField(max_digits=6, decimal_places=2)
    start_date = models.DateField(default=timezone.now)
    base_monthly_payment = models.DecimalField(max_digits=12, decimal_places=2)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FinanceTransaction(models.Model):
    EXPENSE = "expense"
    SALE = "sale"
    TRANSACTION_CHOICES = [
        (EXPENSE, "Expense"),
        (SALE, "Sale"),
    ]

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_CHOICES)
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(blank=True, null=True)
    unit_sale_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    profit = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]


class DebtPaymentOverride(models.Model):
    debt = models.ForeignKey(DebtAccount, on_delete=models.CASCADE, related_name="payment_overrides")
    year_month = models.CharField(max_length=7)
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year_month"]
        constraints = [
            models.UniqueConstraint(fields=["debt", "year_month"], name="unique_debt_month_override")
        ]


class MonthlyBudget(models.Model):
    year_month = models.CharField(max_length=7, unique=True)
    planned_amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year_month"]
