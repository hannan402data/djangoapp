from django.shortcuts import redirect
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class SeparateUserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.debug(f"Request path: {request.path}")
        
        # List of admin URLs
        admin_urls = ['/admin/', '/admin/login/', '/admin/logout/']
        
        # Check if it's an admin URL
        is_admin_url = any(request.path.startswith(url) for url in admin_urls)
        
        if is_admin_url:
            request.session.key_prefix = 'admin'
        else:
            request.session.key_prefix = 'user'
            
            if not request.user.is_authenticated and request.path != reverse('login'):
                logger.debug("User not authenticated, redirecting to login.")
                return redirect('login')  # Redirect to the login page if not authenticated
        
        response = self.get_response(request)
        return response 