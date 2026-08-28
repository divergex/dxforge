import uvicorn

import service

if __name__ == "__main__":
    uvicorn.run(service.app, host="127.0.0.1", port=8000)
