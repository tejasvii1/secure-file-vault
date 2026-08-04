from fastapi import FastAPI # imports FAstAPi class from library we isntalled 

from database import create_db_and_tables

app = FastAPI() # creates app instance; this app object is what Uvicorn will run

@app.on_event("startup") #decorator telling FastAPI to run this function once, right when the server starts, before it accepts any requests
def on_startup(): 
    create_db_and_tables() #builds vault.db and creates user, file, auditlog tables based on the calsses in models.py

@app.get("/") # decorator that registers the function below it to handle GET requests to the / URL
def read_root():
    return {"message": "Secure File Vault API is running"} # function that runs when someone hits that URL; FAstAPi automatically converts the returned Python dictionary into JSONs