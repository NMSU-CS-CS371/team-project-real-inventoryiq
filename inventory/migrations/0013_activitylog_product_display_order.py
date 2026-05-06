from django.db import migrations, models
from django.utils import timezone


def seed_product_order_and_activity(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Expense = apps.get_model("inventory", "Expense")
    PurchaseOrder = apps.get_model("inventory", "PurchaseOrder")
    ActivityLog = apps.get_model("inventory", "ActivityLog")

    products_to_update = []
    current_category = object()
    display_order = 0
    for product in Product.objects.all().order_by("category_id", "name", "id"):
        if product.category_id != current_category:
            current_category = product.category_id
            display_order = 0
        product.display_order = display_order
        products_to_update.append(product)
        display_order += 1
    if products_to_update:
        Product.objects.bulk_update(products_to_update, ["display_order"])

    activity_entries = []
    now = timezone.now()

    for product in Product.objects.all().order_by("created_at", "id"):
        activity_entries.append(
            ActivityLog(
                activity_type="product",
                message=f"Existing product: {product.name}.",
                created_at=product.created_at or product.updated_at or now,
            )
        )

    for expense in Expense.objects.all().order_by("created_at", "id"):
        activity_entries.append(
            ActivityLog(
                activity_type="expense",
                message=f"Existing expense recorded: ${expense.amount}.",
                created_at=expense.created_at or now,
            )
        )

    for order in PurchaseOrder.objects.all().order_by("created_at", "id"):
        activity_entries.append(
            ActivityLog(
                activity_type="purchase_order",
                message=f"Existing purchase order: {order.order_number}.",
                created_at=order.created_at or now,
            )
        )

    if activity_entries:
        ActivityLog.objects.bulk_create(activity_entries)


def remove_seeded_activity(apps, schema_editor):
    ActivityLog = apps.get_model("inventory", "ActivityLog")
    ActivityLog.objects.filter(message__startswith="Existing ").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0012_alter_purchaseorder_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activity_type", models.CharField(max_length=40)),
                ("message", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(seed_product_order_and_activity, remove_seeded_activity),
    ]
