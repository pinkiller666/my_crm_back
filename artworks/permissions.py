from rest_framework.permissions import BasePermission

class IsOwner(BasePermission):
    """
    Доступ к объекту только если request.user == obj.owner
    """
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


# artworks/api/permissions.py
from rest_framework.permissions import BasePermission


class IsArtworkOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsCommissionUser(BasePermission):
    """
    Пример: считаем, что пользователь – это artist.user.
    Если у Commissioner тоже есть связь с User, можно сюда добавить OR.
    """
    def has_object_permission(self, request, view, obj):
        return getattr(obj.artist, 'user', None) == request.user
