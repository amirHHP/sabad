"""Run the search API without the Streamlit UI.

    uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os

from sabad.http_api import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
