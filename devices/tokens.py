from django.contrib.auth.tokens import PasswordResetTokenGenerator

class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # The token will expire if the user's password changes
        # REMOVED user.is_active from hash to prevent invalidation after activation
        return (str(user.pk) + str(timestamp))

email_verification_token = EmailVerificationTokenGenerator()