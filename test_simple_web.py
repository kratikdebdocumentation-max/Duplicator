#!/usr/bin/env python3
"""
Simple web server test
"""

from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting simple web server on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
