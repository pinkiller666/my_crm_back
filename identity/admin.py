from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Artist, ArtistContact, Middleman, Manager, Commissioner, CommissionerContact
from artworks.models import PriceEntry
from common.choices import SocialMediaChoices


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'name', 'email', 'role', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'name', 'email')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('name', 'email', 'role')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'name', 'email', 'password1', 'password2', 'role', 'is_staff', 'is_superuser'),
        }),
    )


# Inline form to add/edit PriceEntry items within the Artist admin page
class PriceEntryInline(admin.TabularInline):
    model = PriceEntry
    extra = 1  # Shows 1 extra blank form for adding new entries
    fields = ('title', 'image')
    min_num = 0
    max_num = 10  # Set a limit on the maximum number of price entries if needed


class ArtistContactInline(admin.TabularInline):
    model = ArtistContact
    extra = 0
    fields = ("social_media", "handle", "url", "notes")
    autocomplete_fields = ()
    show_change_link = True


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "manager_name")
    list_filter = ("manager",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
    inlines = [ArtistContactInline]  # 👈 добавили инлайн

    @admin.display(description="Менеджер")
    def manager_name(self, obj):
        if obj.manager and obj.manager.user:
            full = obj.manager.user.get_full_name()
            if full:
                return full
            return obj.manager.user.username
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "manager__user")


# Middleman Admin
@admin.register(Middleman)
class MiddlemanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'percent')
    search_fields = ('user',)


# Middleman Admin
@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user',)


class CommissionerContactInline(admin.TabularInline):
    model = CommissionerContact
    extra = 1


@admin.register(Commissioner)
class CommissionerAdmin(admin.ModelAdmin):
    list_display = ("name", "paypal_email", "created_at")
    search_fields = ("name", "paypal_email", "notes")
    inlines = [CommissionerContactInline]
