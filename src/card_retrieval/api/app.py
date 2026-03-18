from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from card_retrieval.api.routes import router
from card_retrieval.config import settings

api = FastAPI(
    title="Card Data Retrieval API",
    description="REST API for Thai bank credit card promotion data",
    version="0.1.0",
    docs_url=None,
    redoc_url="/redoc",
)

api.include_router(router)


@api.get("/docs", include_in_schema=False)
def custom_swagger_ui(request: Request) -> HTMLResponse:
    # Get the first configured API key for Swagger pre-auth
    api_key = ""
    if settings.api_keys:
        api_key = settings.api_keys.split(",")[0].strip()

    html = get_swagger_ui_html(
        openapi_url=api.openapi_url or "/openapi.json",
        title=f"{api.title} - Swagger UI",
    )

    if api_key:
        # Inject script to auto-authorize with the API key
        inject = f"""
<script>
window.addEventListener('load', function() {{
    setTimeout(function() {{
        if (window.ui) {{
            window.ui.preauthorizeApiKey('APIKeyHeader', '{api_key}');
        }}
    }}, 500);
}});
</script>
</body>"""
        content = html.body.replace(b"</body>", inject.encode())
        return HTMLResponse(content=content)

    return html
