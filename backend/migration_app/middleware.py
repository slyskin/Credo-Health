class DevCorsMiddleware:
    """
    Minimal permissive CORS middleware for local development only.

    This exercise is explicitly out-of-scope for auth/deployment concerns,
    so rather than pull in django-cors-headers as a dependency, a few
    headers are added by hand. This is NOT suitable for production use.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
