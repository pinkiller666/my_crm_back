from rest_framework import viewsets
from rest_framework.response import Response
from .models import Account, Payment, Payout
from .serializers import AccountSerializer, PaymentSerializer, PayoutSerializer
from rest_framework.views import APIView
from .month_budget_report import get_complete_report
from rest_framework.permissions import IsAuthenticated



class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class PayoutViewSet(viewsets.ModelViewSet):
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
