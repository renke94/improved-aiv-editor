from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from improved_aiv_editor.settings import settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/')
def read_root() -> JSONResponse:
    """Root endpoint."""
    return JSONResponse({'message': 'Hello from Improved AIV Editor!'})

def main() -> None:
    """Main function to run the application."""
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
