from .models import XiaoHongShuVideo
from rest_framework import serializers


class XiaoHongShuVideoSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)


    class Meta:
        model = XiaoHongShuVideo
        fields = "__all__"