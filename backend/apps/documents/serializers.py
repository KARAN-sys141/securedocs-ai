from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "original_filename",
            "status",
            "error_message",
            "visibility",
            "size_bytes",
            "page_count",
            "uploaded_by",
            "created_at",
        ]

    def get_uploaded_by(self, obj):
        return obj.uploaded_by.username if obj.uploaded_by else None


class VisibilitySerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(choices=Document.Visibility.choices)


class GrantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=Document.Visibility.choices,
        default=Document.Visibility.RESTRICTED,
    )
