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

def parse_person(result):
    print(result)
    json_dict = result['u']
    json_dict['id'] = result['id']

    return json_dict

@app.route('/users', methods=['GET', 'POST'])
def handle_users_route():
    if request.method == 'POST':
        return add_user_route()
    else:
        return get_users_route()


def get_users(tx, query):
    results = tx.run(query).data()
    users = [parse_person(result) for result in results]
    return users

def get_users_route():
    with driver.session() as session:
        query = "MATCH (u:User) RETURN u, ID(u) as id"
        users = session.execute_read(get_users, query)

    response = {'users': users}
    return jsonify(response)


def add_user(tx, login):
    query = "MATCH (u:User) WHERE u.login=$login  RETURN u"
    result = tx.run(query, login=login).data()
    if result:
        response = {'message': 'User already exists'}
        return jsonify(response), 404
    else:
        query = "CREATE (u:User {login: $login}) RETURN u, ID(u) as id"
        result = tx.run(query, login=login).data()
        return parse_person(result[0])
        

def add_user_route():
    json_dict = request.get_json(force=True)
    if "login" not in json_dict:
        response = {'message': 'Login not provided'}
        return jsonify(response), 404
    
    login = request.json['login']
    with driver.session() as session:
        return session.execute_write(add_user, login)




if __name__ == '__main__':
    app.run()