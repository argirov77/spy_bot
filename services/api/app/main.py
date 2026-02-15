from fastapi import FastAPI
app = FastAPI(title="Spy Bot API")

@app.get("/")
def root():
    return {"status": "ok"}
