from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Same shape as the FastAPI `UserOut` schema."""

    class Meta:
        model = User
        fields = ["id", "email", "tier", "created_at"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["id", "email", "password", "tier", "created_at"]
        read_only_fields = ["id", "tier", "created_at"]
        # Drop the model's auto UniqueValidator so the duplicate check below
        # is case-insensitive and returns one consistent message.
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate(self, attrs):
        # Run Django's password validators (length, common, numeric-only)
        # against a throwaway user so similarity checks can use the email.
        validate_password(attrs["password"], user=User(email=attrs["email"]))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
