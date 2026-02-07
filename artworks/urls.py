from rest_framework import routers
from .views import ArtworkViewSet, CommissionViewSet, ArtistViewSet

router = routers.DefaultRouter()
router.register(r'artworks', ArtworkViewSet, basename='artwork')
router.register(r'commissions', CommissionViewSet, basename='commission')
router.register(r'artists', ArtistViewSet, basename='artist')

urlpatterns = router.urls
