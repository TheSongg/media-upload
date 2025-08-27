from django.apps import AppConfig


class UploadConfig(AppConfig):
    name = 'media_upload.upload'
    verbose_name = 'upload'
    default_auto_field = 'django.db.models.BigAutoField'