"""Vercel 진입점. Vercel 은 루트 main.py 의 ASGI `app` 을 자동으로 실행한다 (화면 코드는 web/index.py)."""
from web.index import app  # noqa: F401
