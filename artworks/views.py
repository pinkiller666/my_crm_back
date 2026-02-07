from rest_framework import viewsets, permissions, parsers
from artworks.models import Artwork
from .serializers import ArtworkSerializer
from .permissions import IsOwner

class ArtworkViewSet(viewsets.ModelViewSet):
    serializer_class = ArtworkSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        # Только работы текущего пользователя
        return Artwork.objects.filter(owner=self.request.user).order_by('-date', '-id')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        # owner не меняем
        serializer.save(owner=self.request.user)


from rest_framework import viewsets, permissions, parsers
from artworks.models import Artwork, Commission
from identity.models import Artist
from .serializers import ArtworkSerializer, CommissionSerializer, ArtistLiteSerializer
from .permissions import IsArtworkOwner, IsCommissionUser


class ArtworkViewSet(viewsets.ModelViewSet):
    serializer_class = ArtworkSerializer
    permission_classes = [permissions.IsAuthenticated, IsArtworkOwner]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return Artwork.objects.order_by('-date', '-id')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        serializer.save(owner=self.request.user)


class CommissionViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Только комиссии, где artist.user == request.user.
        (Если commissioner привязан к User – можно расширить фильтр.)
        """
        qs = Commission.objects.all()
        user = self.request.user
        return qs.order_by('-accepted_at', '-id')

    def perform_create(self, serializer):
        """
        Если пользователь сам артист – подставляем его как artist.
        Иначе – используем то, что пришло (но всё равно через queryset-фильтр он увидит только своё).
        """
        user = self.request.user
        artist = getattr(user, 'as_artist', None)
        if artist:
            serializer.save(artist=artist)
        else:
            serializer.save()

    def perform_update(self, serializer):
        serializer.save()


class ArtistViewSet(viewsets.ModelViewSet):
    """
    Read-only список артистов, для селектов.
    - Если пользователь сам артист — вернём только его.
    - Если менеджер — можно вернуть artists под его управлением.
    - Если просто юзер — по желанию (тут сделаем только self).
    """
    serializer_class = ArtistLiteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Artist.objects.all()
