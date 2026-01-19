from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

def send_verification_email(user, request):
    """
    Generates a verification token and sends an Onyx-themed HTML email.
    """
    # 1. Generate the security tokens
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # 2. Build the activation link (Points to Vercel Frontend)
    # Ensure FRONTEND_URL is set in settings.py (e.g. https://iotb-frontend.vercel.app)
    activation_link = f"{settings.FRONTEND_URL}/verify-email/{uid}/{token}/"
    
    # 3. Email Configuration
    subject = 'Activate Your EastCoast Bridge Account'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [user.email]

    # 4. HTML Content (EastCoast "Onyx & Cyan" Theme)
    html_content = f"""
    <div style="background-color: #0d1117; color: #ffffff; padding: 40px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; border-radius: 20px; border: 1px solid #30363d;">
        <div style="margin-bottom: 24px;">
            <h1 style="color: #ffffff; font-weight: 300; font-size: 24px; margin: 0;">
                EastCoast <span style="font-weight: bold; color: #00D2FF;">Bridge</span>
            </h1>
            <p style="color: #8b949e; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; margin-top: 4px;">Engineer Initialization Protocol</p>
        </div>
        
        <hr style="border: 0; border-top: 1px solid #30363d; margin: 24px 0;">
        
        <p style="color: #c9d1d9; font-size: 14px; line-height: 1.6;">
            Identity provisioned for <strong>{user.username}</strong>.
            <br>
            To enable access to the telemetry console, you must verify your digital signature.
        </p>

        <div style="margin: 32px 0;">
            <a href="{activation_link}" style="background-color: #00D2FF; color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; display: inline-block; box-shadow: 0 4px 14px rgba(0, 210, 255, 0.4);">
                Initialize Credentials
            </a>
        </div>
        
        <p style="font-size: 10px; color: #484f58; margin-top: 40px;">
            Security ID: {uid}<br>
            If you did not request this access, terminate this message immediately.
        </p>
    </div>
    """
    
    # 5. Send the email (MultiAlternative allows plain text fallback)
    text_content = strip_tags(html_content)
    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()