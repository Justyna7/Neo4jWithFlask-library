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
driver = GraphDatabase.driver(uri, auth=(user, password),database="neo4j")

def error_message(json_dict, values):
    for x in values:
        if x not in json_dict:
            response = {'message': x + ' not provided'}
            return jsonify(response), 404

def check_credentials(tx, login, password):
    query = "MATCH (u:User) WHERE u.login=$login RETURN u, ID(u) as id"
    user = tx.run(query, login=login).data()
    if not user:
        response = {'message': "User doesn't exists"}
        return jsonify(response), 404
    if not bcrypt.checkpw(password, user[0]['u']['password'].encode('ascii')):
        response = {'message': "Wrong password"}
        return jsonify(response), 401

def check_if_book_exists(tx, id):
    query = "MATCH (b:Book) WHERE ID(b)=$id RETURN b"
    book = tx.run(query, id=id).data()
    if not book:
        response = {'message': "Book doesn't exists"}
        return jsonify(response), 404

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
    err = error_message(request.get_json(force=True), ["login","password"])
    if err:
        return err
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
        query = """
            MATCH (b:Book) WITH b 
            MATCH (p:Publishing_House)-[r]-(b)--(a:Author) WITH
            collect(distinct(a{.*, born: toString(a.born)})) as authors, 
            collect(distinct(p{publishing_house:p.name, release_date:toString(r.release_date) })) as published, b
            OPTIONAL MATCH (b)-[r1:RATED]-(u:User) WITH b,r1,u, authors, published
            OPTIONAL MATCH (b)-[r2:RATED]-(a2:Anonymus) WITH [r1]+ [r2] as ratings, b, authors, published
            UNWIND  ratings as rates WITH DISTINCT rates as  ratings, b, authors, published
            WITH b, avg(ratings.rating) as a, authors, published
            ORDER BY a IS NOT NULL DESC
            RETURN b{.*, average_rating:a},authors, published 
        """
        books = session.execute_read(get_books, query)
    response = {'books': books}
    return jsonify(response)

@app.route('/book/<int:id>', methods=['GET'])
def handle_book_route(id):
    return get_book_route(id)

def get_book(tx, query, id):
    err = check_if_book_exists(tx, id)
    if err:
        return err
    results = tx.run(query, id=id).data()
    book = [parse_book(result) for result in results]
    return book[0]

def get_book_route(id):
    with driver.session() as session:
        query = """MATCH (b:Book) WHERE ID(b)=$id WITH b 
            MATCH (p:Publishing_House)-[r]-(b)--(a:Author) WITH
            collect(distinct(a{.*, born: toString(a.born)})) as authors, 
            collect(distinct(p{publishing_house:p.name, release_date:toString(r.release_date) })) as published, b
            OPTIONAL MATCH (b)-[r1:RATED]-(u:User) WITH b,r1,u, authors, published
            OPTIONAL MATCH (b)-[r2:RATED]-(a2:Anonymus) WITH [r1]+ [r2] as ratings, b, authors, published
            UNWIND  ratings as rates WITH DISTINCT rates as  ratings, b, authors, published
            WITH b, avg(ratings.rating) as a, authors, published
            RETURN 
            b{.*, average_rating:a},authors, published"""
        book = session.execute_read(get_book, query, id)
    #response = {'books': books}
    #return jsonify(response)
    return book

def add_comment(tx, login, password, comment, book_id):
    err = check_credentials(tx, login, password)
    if err:
        return err
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
    # query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    # book = tx.run(query, book=book_id).data()
    # if not book:
    #     response = {'message': "Book doesn't exists"}
    #     return jsonify(response), 404
    else:
        query = """MATCH (u:User {login: $login}), (b:Book) WHERE ID(b)=$book 
            CREATE (u)-[c:COMMENTED_ON {comment:$comment}]->(b) 
            RETURN c.comment as comment, ID(c) as id, u.login as login"""
        result = tx.run(query, login=login, book=book_id, comment=comment).data()
        return result[0]

def add_annonymus_comment(tx, comment, book_id):
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
    # query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    # book = tx.run(query, book=book_id).data()
    # if not book:
    #     response = {'message': "Book doesn't exists"}
    #     return jsonify(response), 404
    else:
        print("dxfcghjkmll", book_id, type(book_id), comment, type(comment))
        query = """MATCH (b:Book) WHERE ID(b)=$book 
            WITH b MATCH (a:Anonymus) CREATE (a)-[c:COMMENTED_ON {comment:$comment}]->(b) 
            RETURN c.comment as comment, ID(c) as id, 'Anonymus comment' as login"""
        result = tx.run(query, book=book_id, comment=comment).data()
        print(result)
        return result[0]
    
def get_book_comments(tx, query, id):
    err = check_if_book_exists(tx, id)
    if err:
        return err
    results = tx.run(query, id=id).data()
    comments = [result['comments'] for result in results]
    return comments

def get_book_comments_route(id):
    with driver.session() as session:
        query = """MATCH (b:Book) WHERE ID(b)=$id WITH b OPTIONAL MATCH (b:Book)-[r1:COMMENTED_ON]-(u:User)
            WITH b,u, r1 OPTIONAL MATCH (b)-[r2:COMMENTED_ON]-(a:Anonymus) 
            WITH [r1{.*, login:u.login, id:ID(r1)}] as l1, [r2{.*, login:"Anonymus comment", id:ID(r2)}] as l2 
            WITH l1+ l2 as comments UNWIND comments as c 
            WITH c as comments WHERE comments IS NOT NULL 
            RETURN DISTINCT comments"""
        comments = session.execute_read(get_book_comments, query, id)
    response = {'comments': comments}
    return jsonify(response)


@app.route('/book/<int:id>/comment', methods=['GET', 'POST'])
def handle_comments_route(id):
    if request.method == 'POST':
        return add_comment_route(id)
    else:
        return get_book_comments_route(id)

def add_comment_route(id):
    json_dict = request.get_json(force=True)
    err = error_message(json_dict, ["comment"])
    if err:
        return err
    if "login" in json_dict and "password" not in json_dict:
        response = {'message': 'Password not provided'}
        return jsonify(response), 404
    comment = request.json['comment']
    if "password" in json_dict and "login" in json_dict:
        login = request.json['login']
        password = request.json['password'].encode('ascii')
        with driver.session() as session:
            return session.execute_write(add_comment, login, password, comment, id)
    else:
        with driver.session() as session:
            return session.execute_write(add_annonymus_comment, comment, id)
        

def add_rating(tx, login, password, rating, book_id):
    err = check_credentials(tx, login, password)
    if err:
        return err
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
    # query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    # book = tx.run(query, book=book_id).data()
    # if not book:
    #     response = {'message': "Book doesn't exists"}
    #     return jsonify(response), 404
    else:
        query = """MATCH (u:User {login: $login}), (b:Book) WHERE ID(b)=$book 
            CREATE (u)-[r:RATED {rating:$rating}]->(b) 
            RETURN r.rating as rating, ID(r) as id, u.login as login"""
        result = tx.run(query, login=login, book=book_id, rating=rating).data()
        return result[0]

def add_annonymus_rating(tx, rating, book_id):
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
    # query = "MATCH (b:Book) WHERE ID(b)=$book RETURN b"
    # book = tx.run(query, book=book_id).data()
    # if not book:
    #     response = {'message': "Book doesn't exists"}
    #     return jsonify(response), 404
    else:
        query = """MATCH (b:Book) WHERE ID(b)=$book WITH b MATCH (a:Anonymus) 
            CREATE (a)-[r:RATED {rating:$rating}]->(b) 
            RETURN r.rating as rating, ID(r) as id, 'Anonymus rating' as login""" 
        result = tx.run(query, book=book_id, rating=rating).data()
        return result[0]
        
def get_book_rating(tx, query, id):
    err = check_if_book_exists(tx, id)
    if err:
        return err
    results = tx.run(query, id=id).data()
    ratings = [result['ratings'] for result in results]
    return ratings

def get_book_ratings_route(id):
    with driver.session() as session:
        query = """MATCH (b:Book) WHERE ID(b)=$id WITH b OPTIONAL MATCH (b:Book)-[r1:RATED]-(u:User) 
            WITH b,u, r1 OPTIONAL MATCH (b)-[r2:RATED]-(a:Anonymus) 
            WITH [r1{.*, login:u.login, id:ID(r1)}] as l1, [r2{.*, login:"Anonymus rating", id:ID(r2)}] as l2 
            WITH l1+ l2 as ratings UNWIND ratings as r 
            WITH r as ratings WHERE ratings IS NOT NULL 
            RETURN DISTINCT ratings"""
        ratings = session.execute_read(get_book_rating, query, id)
    response = {'ratings': ratings}
    return jsonify(response)

@app.route('/book/<int:id>/rating', methods=['GET', 'POST'])
def handle_ratings_route(id):
    if request.method == 'POST':
        return add_rating_route(id)
    else:
        return get_book_ratings_route(id)

def add_rating_route(id):
    json_dict = request.get_json(force=True)
    err = error_message(json_dict, ["rating"])
    if err:
        return err
    if "login" in json_dict and "password" not in json_dict:
        response = {'message': 'Password not provided'}
        return jsonify(response), 404
    rating = request.json['rating']
    if "password" in json_dict and "login" in json_dict:
        login = request.json['login']
        password = request.json['password'].encode('ascii')
        with driver.session() as session:
            return session.execute_write(add_rating, login, password, rating, id)
    else:
        with driver.session() as session:
            return session.execute_write(add_annonymus_rating, rating, id)


if __name__ == '__main__':
    app.run()