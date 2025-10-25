from rest_framework.routers import DefaultRouter
from .views import AccountViewSet, PaymentViewSet, PayoutViewSet, BudgetReport
from django.urls import path, include


router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'payouts', PayoutViewSet)

urlpatterns = [

    path('budget/',  BudgetReport.as_view(), name='budget-remaining'),

    # ViewSets (DRF)
    path('', include(router.urls)),
]
