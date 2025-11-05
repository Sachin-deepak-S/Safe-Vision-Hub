# main.py — FastAPI entry point that mounts the app package routes
from fastapi import FastAPI
from app.main import app as inner_app

app = FastAPI(title="NSFW AI Hub - Wrapper")

# include the inner app routers by mounting
app.mount("/", inner_app)
