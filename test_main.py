from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Zororo Portal v4.0 - Root works"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "4.0.0-test"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
