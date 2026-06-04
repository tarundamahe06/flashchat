from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .serializers import (
    RegisterSerializer,
    UserPublicSerializer,
    UserPrivateSerializer,
    ChangePasswordSerializer,
    UserSearchSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )


class MyProfileView(generics.RetrieveUpdateAPIView):
    
    serializer_class = UserPrivateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserProfileView(generics.RetrieveAPIView):
    
    serializer_class = UserPublicSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "username"
    queryset = User.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ChangePasswordView(APIView):
    
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data["old_password"]):
                return Response(
                    {"old_password": "Incorrect password."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FollowToggleView(APIView):
    
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)

        if target == request.user:
            return Response(
                {"error": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cannot follow a user who has blocked you
        if target.is_blocking(request.user):
            return Response(
                {"error": "Unable to follow this user."},
                status=status.HTTP_403_FORBIDDEN
            )

        if request.user.is_following(target):
            request.user.following.remove(target)
            return Response({"status": "unfollowed", "username": target.username})
        else:
            request.user.following.add(target)
            return Response({"status": "followed", "username": target.username})


class BlockToggleView(APIView):
    
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)

        if target == request.user:
            return Response(
                {"error": "You cannot block yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.is_blocking(target):
            # Unblock
            request.user.blocked.remove(target)
            return Response({"status": "unblocked", "username": target.username})
        else:
            # Block — also remove follow relationships in both directions
            request.user.blocked.add(target)
            request.user.following.remove(target)
            target.following.remove(request.user)
            return Response({"status": "blocked", "username": target.username})


class FollowersListView(generics.ListAPIView):
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        return user.followers.all()


class FollowingListView(generics.ListAPIView):
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        return user.following.all()


class BlockedListView(generics.ListAPIView):
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.blocked.all()


class UserSearchView(generics.ListAPIView):
   
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        if not query:
            return User.objects.none()

        # Exclude self and users who have blocked the requester
        blocked_me = self.request.user.blocked_by.all()

        return User.objects.filter(
            Q(username__icontains=query) | Q(full_name__icontains=query)
        ).exclude(
            pk=self.request.user.pk
        ).exclude(
            pk__in=blocked_me
        ).order_by("username")
    




##############



class AllUsersView(generics.ListAPIView):
    """
    GET /api/users/all/
    Returns all users except self and users who blocked the requester.
    """
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        blocked_me = self.request.user.blocked_by.all()
        return User.objects.exclude(
            pk=self.request.user.pk
        ).exclude(
            pk__in=blocked_me
        ).order_by("full_name")