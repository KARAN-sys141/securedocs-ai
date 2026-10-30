from rest_framework import serializers

from .models import Membership


class MembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["organization_id", "organization_name", "role"]


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)
