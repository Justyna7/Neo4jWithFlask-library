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
    json_dict['authors'] = result['authors']
    json_dict['published'] = result['published']
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

def parse_comment(result):
    print(result)
    json_dict = {}
    json_dict["comment"]= result['comment']
    # json_dict 
    json_dict['id']= result['id']
    json_dict['author'] = result['login']
    return json_dict

def add_comment(tx, login, password, comment, book):
    query = "MATCH (u:User) WHERE u.login=$login RETURN u, ID(u) as id"
    user = tx.run(query, login=login).data()
    if not user:
        response = {'message': "User doesn't exists"}
        return jsonify(response), 404
    if not bcrypt.checkpw(password, user[0]['u']['password'].encode('ascii')):
        response = {'message': "Wrong password"}
        return jsonify(response), 401
    query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    book = tx.run(query, book=book).data()
    if not book:
        response = {'message': "Book doesn't exists"}
        return jsonify(response), 404
    #return parse_person(result[0])
    else:
        query = "MATCH (u:User {login: $login}), (b:Book) WHERE ID(b)=$book CREATE (u)-[c:COMMENTED_ON {comment:$comment}]->(b) RETURN c.comment as comment, ID(c) as id, u.login as login"
        result = tx.run(query, login=login, book=book, comment=comment).data()
        return parse_comment(result[0])

def add_annonymus_comment(tx, comment, book_id):
    query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    book = tx.run(query, book=book_id).data()
    if not book:
        response = {'message': "Book doesn't exists"}
        return jsonify(response), 404
    else:
        print("dxfcghjkmll", book_id, type(book_id), comment, type(comment))
        query = "MATCH (b:Book) WHERE ID(b)=$book WITH b MATCH (a:Anonymus) CREATE (a)-[c:COMMENTED_ON {comment:$comment}]->(b) RETURN c.comment as comment, ID(c) as id, 'Anonymus comment' as login" 
        result = tx.run(query, book=book_id, comment=comment).data()
        print(result)
        return parse_comment(result[0])
        
@app.route('/comment', methods=['GET', 'POST'])
def handle_comments_route():
    if request.method == 'POST':
        return add_comment_route()
    # else:
    #     return get_comment_route()

def add_comment_route():
    json_dict = request.get_json(force=True)
    if "book" not in json_dict:
        response = {'message': 'Book not provided'}
        return jsonify(response), 404
    if "comment" not in json_dict:
        response = {'message': 'Comment not provided'}
        return jsonify(response), 404
    if "login" in json_dict and "password" not in json_dict:
        response = {'message': 'Password not provided'}
        return jsonify(response), 404
    comment = request.json['comment']
    book = request.json['book']
    if "password" in json_dict and "login" in json_dict:
        login = request.json['login']
        password = request.json['password'].encode('ascii')
        with driver.session() as session:
            return session.execute_write(add_comment, login, password, comment, book)
    else:
        with driver.session() as session:
            return session.execute_write(add_annonymus_comment, comment, book)
        



if __name__ == '__main__':
    app.run()