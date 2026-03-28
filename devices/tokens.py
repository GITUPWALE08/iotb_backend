from django.utils import timezone
import hashlib
import secrets
import base64

class EmailVerificationTokenGenerator:
    def make_token(self, user):
        """
        Generate a custom token without one-time use limitation
        """
        timestamp = str(int(timezone.now().timestamp()))
        hash_value = self._make_hash_value(user, timestamp)
        
        # Create token similar to Django's format but without one-time use
        token = base64.urlsafe_b64encode(
            f"{timestamp}:{hash_value}".encode()
        ).decode()
        
        return token
    
    def _make_hash_value(self, user, timestamp):
        """
        Create hash without user.is_active dependency
        """
        data = f"{user.pk}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def check_token(self, user, token):
        """
        Check token without one-time use consumption
        """
        try:
            # Decode token
            decoded = base64.urlsafe_b64decode(token).decode()
            timestamp_str, hash_value = decoded.split(':')
            
            # Verify timestamp (24-hour expiry)
            try:
                ts = int(timestamp_str)
                token_age = timezone.now().timestamp() - ts
                if token_age > 86400:  # 24 hours
                    return False
            except (ValueError, IndexError):
                return False
            
            # Verify hash
            expected_hash = self._make_hash_value(user, ts)
            return secrets.compare_digest(hash_value.encode(), expected_hash.encode())
            
        except (ValueError, TypeError, IndexError):
            return False

# Create custom instance
email_verification_token = EmailVerificationTokenGenerator()