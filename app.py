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


def parse_book(result):
    print(result)
    json_dict = result['b']
    # json_dict['id'] = result['b_id']
    json_dict['authors'] = result['authors']
    json_dict['published'] = result['published']
    # json_dict['published']['publishing house'] = result['p']["name"]
    # json_dict['published']['release date'] = result['r']
    # json_dict['author']["name"] = result['a']["name"]
    # json_dict['author']["surname"] = result['a']["surname"]
    # json_dict['author']["born"] = Date(result['a']["born"])
    # json_dict['author']['id'] = result['a_id']
    return json_dict


@app.route('/books', methods=['GET', 'POST'])
def handle_books_route():
    # if request.method == 'POST':
    #     return add_book_route()
    # else:
        return get_books_route()


def get_books(tx, query):
    results = tx.run(query).data()
    books = [parse_book(result) for result in results]
    return books

def get_books_route():
    with driver.session() as session:
        query = 'MATCH (p:Publishing_House)-[r]-(b:Book)--(a:Author) RETURN b, collect(distinct(a{.*, born: toString(a.born)})) as authors, collect(distinct(p{publishing_house:p.name, release_date:toString(r.release_date) })) as published'
        books = session.execute_read(get_books, query)

    response = {'books': books}
    return jsonify(response)


        



if __name__ == '__main__':
    app.run()