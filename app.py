from flask import Flask, jsonify, request, json
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os #provides ways to access the Operating System and allows us to read the environment variables
import bcrypt

load_dotenv()

app = Flask(__name__)

uri = os.getenv('URI')
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("PASSWORD")
#print(uri, user, password)
driver = GraphDatabase.driver(uri, auth=(user, password),database="neo4j")

def parse_person(result):
    print(result)
    json_dict = {}
    json_dict['login']= result['u']['login']
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


def add_user(tx, login, password):
    query = "MATCH (u:User) WHERE u.login=$login  RETURN u"
    result = tx.run(query, login=login).data()
    if result:
        response = {'message': 'User already exists'}
        return jsonify(response), 404
    else:
        query = "CREATE (u:User {login: $login, password:$password}) RETURN u, ID(u) as id"
        passw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('ascii')
        print(passw)
        result = tx.run(query, login=login, password = passw).data()
        return parse_person(result[0])
        

def add_user_route():
    json_dict = request.get_json(force=True)
    if "login" not in json_dict:
        response = {'message': 'Login not provided'}
        return jsonify(response), 404
    if "password" not in json_dict:
        response = {'message': 'Password not provided'}
        return jsonify(response), 404
    login = request.json['login']
    password = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(add_user, login, password)





if __name__ == '__main__':
    app.run()