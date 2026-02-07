from rest_framework import serializers
from .models import Commission, ReferenceImage



from rest_framework import serializers
from artworks.models import Artwork, Commission
from identity.models import Artist
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

# artworks/api/serializers.py (продолжение)
class ArtworkSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    final_image_url = serializers.SerializerMethodField(read_only=True)
    commission_name = serializers.ReadOnlyField(source='commission.name')

    class Meta:
        model = Artwork
        fields = [
            'id',
            'owner',
            'final_image',
            'final_image_url',
            'description',
            'type',
            'purpose',
            'slot',
            'date',
            'status',
            'commission',
            'commission_name',
            'expected_completion_date',
            'actual_completion_date',
        ]
        read_only_fields = ['id', 'owner', 'final_image_url', 'commission_name']

    def get_final_image_url(self, obj):
        request = self.context.get('request')
        if obj.final_image and hasattr(obj.final_image, 'url'):
            return request.build_absolute_uri(obj.final_image.url) if request else obj.final_image.url
        return None




class ArtistLiteSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = ['id', 'display_name']

    def get_display_name(self, obj):
        return str(obj)


class CommissionSerializer(serializers.ModelSerializer):
    artist_name = serializers.ReadOnlyField(source='artist.__str__')
    commissioner_name = serializers.ReadOnlyField(source='commissioner.__str__')

    class Meta:
        model = Commission
        fields = [
            'id',
            'name',
            'artist',
            'artist_name',
            'commissioner',
            'commissioner_name',
            'amount',
            'currency',
            'accepted_at',
            'description',
        ]
        read_only_fields = ['id', 'accepted_at', 'artist_name', 'commissioner_name']
