from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class Category(models.Model):
    # a category is basically just a folder to organize products into. you can have subcategories too
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    def __str__(self):
        # returns the category name, but shows the parent category too if it's a subcategory
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]


class Product(models.Model):
    # a product is basically anything in the inventory - has a name, quantity, category, and prices
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
        # just returns the product name so it looks nice in admin and forms
        return self.name

    @property
    def is_low_stock(self):
        # checks if the product is running low on stock (less than or equal to the threshold)
        return self.quantity <= self.low_stock_threshold


class Expense(models.Model):
    # just tracks expenses like rent, utilities, etc for the finance page
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        # shows the expense amount and date nicely
        return f"Expense ${self.amount} on {self.date}"


class DebtAccount(models.Model):
    # tracks debts like loans or credit card balances, with interest rates and payment info
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
        # just returns the debt account name
        return self.name


class FinanceTransaction(models.Model):
    # tracks all money stuff - like sales and expenses with amounts and dates
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
    # lets you set a custom payment amount for a specific month instead of the regular one
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
    # sets a budget amount for each month
    year_month = models.CharField(max_length=7, unique=True)
    planned_amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year_month"]


class PurchaseOrder(models.Model):
    # an order you create to buy stuff from suppliers. has items, dates, and a status
    SUPPLIER_CHOICES = [
        ('company_a', 'Company A'),
        ('company_b', 'Company B'),
        ('company_c', 'Company C'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('received', 'Received'),
    ]
    supplier = models.CharField(max_length=50, choices=SUPPLIER_CHOICES)
    order_number = models.CharField(max_length=100, unique=True)
    note = models.TextField(blank=True, default='')
    delivery_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        # shows the order number and supplier name
        return f"{self.order_number} ({self.get_supplier_display()})"


class PurchaseOrderItem(models.Model):
    # a single line item in a purchase order - like "5 keyboards" or "10 monitors"
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        # shows the product name and how many we're ordering
        return f"{self.product.name} x{self.quantity}"

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gte=1), name='purchaseorderitem_quantity_gte_1'),
            models.UniqueConstraint(
                fields=['purchase_order', 'product'],
                name='unique_product_per_purchase_order'
            )
        ]
