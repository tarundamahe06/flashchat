from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ["id", "full_name", "username", "email", "password", "password2", "bio"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            bio=validated_data.get("bio", ""),
            password=validated_data["password"],
        )
        return user


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Used when viewing another user's profile.
    Shows public info + follow/block status relative to request user.
    """
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "username",
            "bio",
            "followers_count",
            "following_count",
            "is_following",
            "is_blocked",
        ]

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.is_following(obj)
        return False

    def get_is_blocked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.is_blocking(obj)
        return False


class UserPrivateSerializer(serializers.ModelSerializer):
    """
    Used when the user views/edits their own profile.
    """
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "username",
            "email",
            "bio",
            "followers_count",
            "following_count",
        ]
        read_only_fields = ["id", "username", "email"]

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password": "New passwords do not match."})
        return attrs


class UserSearchSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer used in search results.
    """
    class Meta:
        model = User
        fields = ["id", "full_name", "username", "bio"]