from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        # password=None -> unusable password (the FastAPI app stored NULL for
        # OAuth-only accounts; Django's equivalent is an unusable hash).
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-identified user, mirroring the FastAPI `users` table.

    `tier` lives on the user here; in the FastAPI app it lives on the user's
    personal workspace (workspaces are not ported, see README).
    """

    class Tier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"

    email = models.EmailField(unique=True)
    tier = models.CharField(max_length=8, choices=Tier.choices, default=Tier.FREE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email
