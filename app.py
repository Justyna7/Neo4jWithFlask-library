from flask import Flask, jsonify, request, json
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os #provides ways to access the Operating System and allows us to read the environment variables

load_dotenv()

app = Flask(__name__)

uri = os.getenv('URI')
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("PASSWORD")
#print(uri, user, password)
driver = GraphDatabase.driver(uri, auth=(user, password),database="neo4j")

if __name__ == '__main__':
    app.run()