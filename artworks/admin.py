from django.contrib import admin
from django import forms
from django.forms.widgets import ClearableFileInput

from .models import Commission, Artwork, ReferenceImage
from .admin_helpers import ReferenceInline

from accounting.models import Payment
from identity.models import Commissioner, CommissionerContact


class PaymentInline(admin.TabularInline):
    model = Payment  # FK: payment.commission
    extra = 0
    readonly_fields = ('amount', 'currency', 'pay_system')
    # если FK у Payment называется не 'commission', укажи: fk_name = 'commission'


class MultipleClearableFileInput(ClearableFileInput):
    allow_multiple_selected = True


class MonthYearFilter(admin.SimpleListFilter):
    title = "месяц и год"
    parameter_name = "month_year"

    def lookups(self, request, model_admin):
        dates = Commission.objects.dates("accepted_at", "month", order="DESC")
        return [(d.strftime("%Y-%m"), d.strftime("%B %Y")) for d in dates]

    def queryset(self, request, queryset):
        if self.value():
            year, month = map(int, self.value().split("-"))
            return queryset.filter(accepted_at__year=year, accepted_at__month=month)
        return queryset


class BulkRefsUploadForm(forms.ModelForm):
    # если хочешь мультизагрузку — поменяй виджет на MultipleClearableFileInput
    bulk_images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput
    )

    class Meta:
        model = Commission
        exclude = ('accepted_at',)


class ReferenceImageInline(admin.TabularInline):
    model = ReferenceImage
    extra = 0
    fields = ('image', 'kind', 'caption', 'source_url', 'order', 'uploaded_by', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('order', 'id')


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    form = BulkRefsUploadForm
    inlines = [ReferenceInline, PaymentInline]

    list_display = ('id', 'name', 'artist', 'amount', 'accepted_at')
    list_filter = ('artist', MonthYearFilter)
    # artist.name поля нет — ищем по связанному пользователю артиста
    search_fields = (
        'id',
        'artist__user__username',
        'artist__user__first_name',
        'artist__user__last_name',
        'artist__user__name',  # если поле name в кастомном User есть
    )
    autocomplete_fields = ('artist',)
    date_hierarchy = 'accepted_at'
    readonly_fields = ('accepted_at',)

    fields = ('name', 'artist', 'commissioner', 'amount', 'description', 'accepted_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('artist__user', 'commissioner').prefetch_related('references')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        files = request.FILES.getlist('bulk_images')
        if files:
            last_order = obj.references.order_by('-order').values_list('order', flat=True).first() or 0
            order = last_order + 1
            for f in files:
                ReferenceImage.objects.create(
                    commission=obj,
                    image=f,
                    order=order,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )
                order += 1


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    list_display = ('id', 'commission', 'type', 'status', 'expected_completion_date', 'actual_completion_date')
    list_filter = ('status', 'type')
    search_fields = (
        'id',
        'commission__commissioner__name',
        'commission__artist__user__username',
        'commission__artist__user__name',
    )
    autocomplete_fields = ('commission',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('commission', 'commission__artist__user', 'commission__commissioner')



