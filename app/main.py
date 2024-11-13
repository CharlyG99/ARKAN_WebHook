from fastapi import FastAPI
from routes.trading_routes import router as tradingrouter
from utils.mongo import mongo
import logging
from dotenv import load_dotenv
import os
from config import settings
import uvicorn


app = FastAPI()
logger = logging.getLogger(__name__)
api = None
load_dotenv()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up and connecting to MongoDB")
    # MongoDB connection is already initialized in the mongo module

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down and closing MongoDB connection")
    await mongo.close()


@app.get("/")
async def root():
    return {"message": "Welcome to the Template Microservice v0.1.10"}


app.include_router(tradingrouter, prefix="/trade")


