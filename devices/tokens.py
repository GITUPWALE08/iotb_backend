from django.contrib.auth.tokens import PasswordResetTokenGenerator

class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # The token will expire if the user's active status or password changes
        return (str(user.pk) + str(timestamp) + str(user.is_active))

email_verification_token = EmailVerificationTokenGenerator()