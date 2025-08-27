from django.db import models


class XiaoHongShuVideo(models.Model):
    title = models.CharField(max_length=100)
    create_time = models.DateTimeField(auto_now_add=True)
