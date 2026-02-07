from rest_framework import viewsets
from rest_framework.response import Response
from .models import Account, Payment, Payout
from .serializers import AccountSerializer, PaymentSerializer, PayoutSerializer
from rest_framework.views import APIView
from .month_budget_report import get_complete_report
from rest_framework.permissions import IsAuthenticated



from rest_framework import viewsets, permissions

from .models import Account, Payment, Payout
from .serializers import AccountSerializer, PaymentSerializer, PayoutSerializer


class UserOwnedViewSet(viewsets.ModelViewSet):
    """
    Base viewset that:
    - requires authentication
    - limits all queries to request.user
    - automatically sets user on create
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # self.queryset MUST be defined in subclasses
        assert self.queryset is not None, (
            f"{self.__class__.__name__} is missing a queryset. "
            "Define queryset or override get_queryset completely."
        )
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AccountViewSet(UserOwnedViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class PaymentViewSet(UserOwnedViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class PayoutViewSet(UserOwnedViewSet):
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer

class BudgetReport(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        year = int(request.query_params.get('year', 2025))
        month = int(request.query_params.get('month', 9))

        # основной бюджетный отчёт
        budget_report = get_complete_report(user, month, year, )

        return Response(budget_report)
