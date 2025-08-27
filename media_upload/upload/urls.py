from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .redbook import RedBookUpdateViewSet



router = DefaultRouter()
router.register(r'redbook', RedBookUpdateViewSet, basename='redbook')


urlpatterns = [
    path('', include(router.urls)),
]