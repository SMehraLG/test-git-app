from fastapi import FastAPI
from smoke_python import add, subtract

app = FastAPI()


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "smoke-python", "ops": ["add", "subtract"]}


@app.get("/add")
def add_numbers(a: int, b: int):
    return {"result": add(a, b)}


@app.get("/subtract")
def subtract_numbers(a: int, b: int):
    return {"result": subtract(a, b)}
