"""User accounts and login sessions (standard library only: PBKDF2 hashing + random tokens)."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta

from hydrohome.errors import AuthError, ConflictError, ValidationError

PBKDF2_ROUNDS = 200_000
TOKEN_DAYS = 7
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FMT = "%Y-%m-%d %H:%M:%S"


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, rounds, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"],
            "created_at": user["created_at"]}


class AuthService:
    def __init__(self, users, tokens, memberships):
        self.users, self.tokens, self.memberships = users, tokens, memberships

    @staticmethod
    def _check_password(password):
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters.")
        if len(password) > 128:
            raise ValidationError("Password must be at most 128 characters.")

    def _issue_token(self, user_id):
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        self.tokens.purge_expired(now.strftime(_FMT))
        self.tokens.add(_token_hash(token), user_id,
                        (now + timedelta(days=TOKEN_DAYS)).strftime(_FMT))
        return token

    def register(self, name, email, password):
        name, email = name.strip(), email.strip().lower()
        errors = []
        if not name:
            errors.append("Name is required.")
        if not _EMAIL.match(email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if errors:
            raise ValidationError(errors)
        if self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists.")
        first_user = self.users.count() == 0
        user_id = self.users.add(name, email, hash_password(password))
        if first_user:
            # Adopt households created earlier by the desktop app so no data is orphaned.
            for household in self.memberships.unowned_households():
                self.memberships.link(household["id"], user_id, "admin")
        return public_user(self.users.get(user_id)), self._issue_token(user_id)

    def login(self, email, password):
        user = self.users.get_by_email(email.strip().lower())
        if not user or not verify_password(password, user["password_hash"]):
            raise AuthError("Incorrect email or password.")
        return public_user(user), self._issue_token(user["id"])

    def user_for_token(self, token):
        record = self.tokens.get(_token_hash(token)) if token else None
        if not record or record["expires_at"] < datetime.now().strftime(_FMT):
            raise AuthError("Please sign in again.")
        user = self.users.get(record["user_id"])
        if not user:
            raise AuthError("Please sign in again.")
        return user

    def logout(self, token):
        self.tokens.delete(_token_hash(token))

    def update_profile(self, user_id, name):
        name = name.strip()
        if not name or len(name) > 60:
            raise ValidationError("Name is required (max 60 characters).")
        self.users.update_name(user_id, name)
        return public_user(self.users.get(user_id))

    def change_password(self, user_id, current, new):
        user = self.users.get(user_id)
        if not verify_password(current, user["password_hash"]):
            raise ValidationError("Current password is incorrect.")
        self._check_password(new)
        self.users.update_password(user_id, hash_password(new))
