import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ActivityLog, Category, Expense, Product, PurchaseOrder


class InventoryIQUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.client.force_login(self.user)

    def test_expense_delete_updates_total_and_logs_activity(self):
        Expense.objects.create(amount=Decimal("25.00"), note="Packing supplies")

        expense = Expense.objects.create(amount=Decimal("15.00"), note="Postage")
        response = self.client.post(reverse("expense_delete", args=[expense.pk]))

        self.assertRedirects(response, reverse("finances"))
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())
        self.assertTrue(
            ActivityLog.objects.filter(
                activity_type="expense",
                message="Removed expense: $15.00.",
            ).exists()
        )

        response = self.client.get(reverse("finances"))
        self.assertEqual(response.context["expenses_total"], Decimal("25.00"))

    def test_product_reorder_persists_order_without_changing_category(self):
        category = Category.objects.create(name="Keyboards")
        first = Product.objects.create(name="Alpha", category=category, display_order=0)
        second = Product.objects.create(name="Beta", category=category, display_order=1)

        response = self.client.post(
            reverse("product_reorder"),
            {"product_order": f"{second.pk},{first.pk}"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.category, category)
        self.assertEqual(second.category, category)
        self.assertEqual(first.display_order, 1)
        self.assertEqual(second.display_order, 0)
        self.assertTrue(ActivityLog.objects.filter(message="Reordered products in Keyboards.").exists())

    def test_product_drag_can_move_from_uncategorized_to_category(self):
        category = Category.objects.create(name="Clothing")
        product = Product.objects.create(name="Hat", category=None, display_order=0)

        response = self.client.post(
            reverse("product_reorder"),
            data=json.dumps(
                {
                    "groups": [
                        {"category_id": category.id, "product_ids": [product.id]},
                        {"category_id": None, "product_ids": []},
                    ]
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.category, category)
        self.assertEqual(product.display_order, 0)
        self.assertTrue(
            ActivityLog.objects.filter(
                message="Moved Hat from Uncategorized to Clothing."
            ).exists()
        )

    def test_product_drag_can_move_between_categories_without_losing_order(self):
        clothing = Category.objects.create(name="Clothing")
        accessories = Category.objects.create(name="Accessories")
        hat = Product.objects.create(name="Hat", category=clothing, display_order=0)
        belt = Product.objects.create(name="Belt", category=accessories, display_order=0)

        response = self.client.post(
            reverse("product_reorder"),
            data=json.dumps(
                {
                    "groups": [
                        {"category_id": clothing.id, "product_ids": []},
                        {"category_id": accessories.id, "product_ids": [belt.id, hat.id]},
                    ]
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        hat.refresh_from_db()
        belt.refresh_from_db()
        self.assertEqual(hat.category, accessories)
        self.assertEqual(hat.display_order, 1)
        self.assertEqual(belt.display_order, 0)

    def test_dashboard_activity_center_shows_only_past_week(self):
        old_activity = ActivityLog.objects.create(
            activity_type="product",
            message="Old change.",
            created_at=timezone.now() - timedelta(days=8),
        )
        recent_activity = ActivityLog.objects.create(
            activity_type="expense",
            message="Recent change.",
            created_at=timezone.now() - timedelta(days=2),
        )

        response = self.client.get(reverse("dashboard"))

        activity_items = list(response.context["activity_items"])
        self.assertIn(recent_activity, activity_items)
        self.assertNotIn(old_activity, activity_items)
        self.assertContains(response, "Recent change.")
        self.assertNotContains(response, "Old change.")

    def test_dashboard_finance_position_includes_expense_breakdown(self):
        Expense.objects.create(amount=Decimal("45.50"), note="Rent")

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Expense Breakdown")
        self.assertContains(response, "Rent")
        self.assertEqual(list(response.context["recent_expenses"])[0].amount, Decimal("45.50"))

    def test_product_list_renders_collapsible_sortable_groups(self):
        category = Category.objects.create(name="Monitors")
        empty_category = Category.objects.create(name="Empty")
        Product.objects.create(name="Display A", category=category, display_order=0)

        response = self.client.get(reverse("product_list"))

        self.assertContains(response, "Expand all")
        self.assertContains(response, "Display A")
        self.assertContains(response, "product-sortable-list")
        self.assertContains(response, f'data-category-id="{empty_category.id}"')
        self.assertContains(response, "Drop a product here to move it into Empty.")

    def test_search_suggestions_include_finances_page(self):
        response = self.client.get(
            reverse("global_search_suggestions"),
            {"q": "finance"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(any(result["title"] == "Finances" for result in results))

    def test_search_suggestions_include_product_context(self):
        category = Category.objects.create(name="Clothing")
        product = Product.objects.create(
            name="Hat",
            category=category,
            quantity=4,
            sku_number="HAT-001",
        )

        response = self.client.get(
            reverse("global_search_suggestions"),
            {"q": "hat"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        results = response.json()["results"]
        product_result = next(result for result in results if result["title"] == "Hat")
        self.assertEqual(product_result["type"], "Product")
        self.assertIn("Clothing", product_result["subtitle"])
        self.assertIn("Qty 4", product_result["subtitle"])
        self.assertIn("HAT-001", product_result["subtitle"])
        self.assertIn(f"highlight_product={product.id}", product_result["url"])

    def test_global_search_results_group_records(self):
        category = Category.objects.create(name="Hat Category")
        Product.objects.create(name="Hat", category=category)
        PurchaseOrder.objects.create(
            supplier="company_a",
            order_number="PO-HAT",
            note="Hat shipment",
        )
        Expense.objects.create(amount=Decimal("12.00"), note="Hat display")

        response = self.client.get(reverse("global_search"), {"q": "hat"})

        self.assertContains(response, "Products")
        self.assertContains(response, "Categories")
        self.assertContains(response, "Purchase Orders")
        self.assertContains(response, "Expenses")
        self.assertContains(response, "Hat")
        self.assertContains(response, "Hat Category")
        self.assertContains(response, "PO-HAT")
        self.assertContains(response, "Hat display")
