from rest_framework import serializers
from .models import Commission, ReferenceImage


class ReferenceReadSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceImage
        fields = ["id", "kind", "caption", "source_url", "order", "image_url"]

    def get_image_url(self, obj):
        req = self.context.get("request")
        try:
            return req.build_absolute_uri(obj.image.url) if (req and obj.image) else None
        except Exception:
            return None


class CommissionReadSerializer(serializers.ModelSerializer):
    # покажем человека “как строку” (берётся из __str__), чтобы фронту было удобно
    artist = serializers.StringRelatedField()
    client = serializers.StringRelatedField()
    # вложенные референсы read-only
    references = ReferenceReadSerializer(many=True, read_only=True)

    class Meta:
        model = Commission
        fields = [
            "id", "name", "artist", "client",
            "amount", "description", "accepted_at",
            "references",
        ]
