from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ActivityLog, Category, Expense, Product


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
        Product.objects.create(name="Display A", category=category, display_order=0)

        response = self.client.get(reverse("product_list"))

        self.assertContains(response, "Expand all")
        self.assertContains(response, "Display A")
        self.assertContains(response, "product-sortable-list")
