from rest_framework import serializers
from .models import User, Middleman, Manager, Artist


class MiddlemanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Middleman
        fields = ['percent', 'paypal_address']


class ManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manager
        fields = []  # тут пока пусто, можно добавить поля, если надо


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = []  # тоже пусто, можно добавить поля


class UserSerializer(serializers.ModelSerializer):
    middleman_profile = MiddlemanSerializer(read_only=True)
    as_manager = ManagerSerializer(read_only=True)
    as_artist = ArtistSerializer(read_only=True)

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'role', 'roles', 'middleman_profile', 'as_manager', 'as_artist']

    def get_roles(self, obj):
        roles = []
        try:
            if obj.as_artist:
                roles.append("artist")
        except Artist.DoesNotExist:
            pass

        try:
            if obj.as_manager:
                roles.append("manager")
        except Manager.DoesNotExist:
            pass

        try:
            if obj.middleman_profile:
                roles.append("middleman")
        except Middleman.DoesNotExist:
            pass

        if obj.is_superuser:
            roles.append("admin")

        return roles
