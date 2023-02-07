from flask import Flask, jsonify, request, json
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os #provides ways to access the Operating System and allows us to read the environment variables
import bcrypt
from  error_handling import *
load_dotenv()

app = Flask(__name__)

uri = os.getenv('URI')
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("PASSWORD")
driver = GraphDatabase.driver(uri, auth=(user, password),database="neo4j")

def initiate_request(needed_values, request, f):
    print("intiate without id")
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(f, data)

def initiate_request_with_id(needed_values, request, f, id):
    print("intiate with id", id)
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(f, data, id)

def parse_person(result, c):
    print(result)
    json_dict = {}
    json_dict['login']= result[c]['login']
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
    users = [parse_person(result, "u") for result in results]
    return users

def get_users_route():
    with driver.session() as session:
        query = "MATCH (u:User) RETURN u, ID(u) as id"
        users = session.execute_read(get_users, query)
    response = {'users': users}
    return jsonify(response)

def add_user(tx, data):
    login = data["login"]
    password = data["password"]
    query = "MATCH (u:User) WHERE u.login=$login  RETURN u"
    result = tx.run(query, login=login).data()
    if result:
        response = {'message': 'User already exists'}
        return jsonify(response), 404
    else:
        query = "CREATE (u:User {login: $login, password:$password}) RETURN u, ID(u) as id"
        passw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('ascii')
        result = tx.run(query, login=login, password = passw).data()
        return parse_person(result[0], "u")
        
def add_user_route():
    needed_values = ["login","password"]
    return initiate_request(needed_values, request, add_user)


def edit_user(tx, data):
    login = data["login"]
    err = check_credentials(login, data["password"])
    if err:
        return err
    password = data["new_pass"]
    query = "MATCH (u:User {login: $login}) SET u.password=$password RETURN u, ID(u) as id"
    passw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('ascii')
    result = tx.run(query, login=login, password = passw).data()
    return parse_person(result[0], "u")

@app.route('/users', methods=['PUT'])        
def edit_user_route():
    needed_values = ["login","password", "new_pass"]
    return initiate_request(needed_values, request, edit_user)

def parse_book(result):
    print(result)
    json_dict = result['b']
    json_dict['authors'] = result['authors']
    json_dict['published'] = result['published']
    return json_dict


@app.route('/books', methods=['GET', 'POST'])
def handle_books_route():
    if request.method == 'POST':
        return add_book_route()
    else:
        return get_books_route()


def add_book(tx, data):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = "MATCH (p:Publishing_House {name:$publishing_house}) RETURN p, ID(p) as id"
    result = tx.run(query, publishing_house=data["publishing_house"]).data()
    if not result:
        response = {'message': "Publishing House with name %s doesn't exists in database" % (data["publishing_house"])}
        return jsonify(response), 404
    ph_id = result[0]["id"]
    query = "MATCH (a:Author {name:$author_name, surname: $author_surname}) RETURN a, ID(a) as id"
    result = tx.run(query, author_name=data["author_name"], author_surname=data["author_surname"]).data()
    if not result:
        response = {'message': "Author with name %s and surname %s doesn't exists in database" % (data["author_name"], data["author_surname"])}
        return jsonify(response), 404
    author_id = result[0]["id"]
    query = """MATCH (a:Author)--(b:Book{title:$title}) WHERE ID(a) = $author_id RETURN ID(b) as id"""
    result = tx.run(query, author_id=author_id, title=data["title"]).data()
    if result:
        response = {'message': "Book already exists"}
        return jsonify(response), 404
    query = """MATCH (a:Author) WHERE ID(a) = $author_id WITH a MATCH (p:Publishing_House) WHERE ID(p) = $ph_id WITH a, p
    CREATE (b:Book {title: $title, cover_photo: $cover_photo, genres:$genres, description:$description, number:$number})
    CREATE (a)<-[:WRITTEN_BY]-(b)-[:RELEASED_BY {release_date:date($release_date)}]->(p) RETURN ID(b) as id"""
    result = tx.run(query, author_id=author_id, ph_id=ph_id, 
        title=data["title"], cover_photo=data["cover_photo"],genres=data["genres"], description=data["description"], number=data["number"],release_date=data["release_date"]  ).data()
    return jsonify({"Book added under id":result}), 200
        
def add_book_route():
    # err = no_json_error_message(request)
    # if err:
    #     return err
    needed_values=["login","password", "title", "genres", "description", "author_name", "author_surname", "release_date", "publishing_house", "number"]
    err = initiate_request_error_message(request, needed_values)
    # err = error_message(json_dict, needed_values)
    if err:
        return err
    json_dict = request.get_json(force=True)
    cover_photo = (request.json["cover_photo"] if "cover_photo" in json_dict else "")
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["cover_photo"] = cover_photo
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(add_book, data)

def get_books(tx, query, data):
    if data['genres'] != "":
        results = tx.run(query, title = data["title"], genres=data["genres"], name = data["name"], surname = data["surname"]).data()
    else:
        results = tx.run(query, title = data["title"], name = data["name"], surname = data["surname"]).data()
    books = [parse_book(result) for result in results]
    return books

def get_books_route():
    data = {"title":"", "name":"", "surname":"","genres":"", "sort":""}
    genres = ""
    sort = "ORDER BY a IS NOT NULL DESC "
    if request.data != b'':
        json_dict = request.get_json(force=True)
        # data = ["title", "name", "surname","genres"]
        data = {x:request.json[x] if x in json_dict else "" for x in data}
        if data['genres'] != "":
            genres = "AND ANY(genre IN $genres WHERE genre IN b.genres)"
        if data['sort'] == "alphabet":
            sort = "ORDER BY b.title "
        if data['sort'] == "new":
            sort = "ORDER BY published[0].release_date IS NOT NULL DESC "
    print(data)
    with driver.session() as session:
        query = "MATCH (b:Book) WHERE tolower(b.title) CONTAINS tolower($title) " + genres + """WITH b 
            MATCH (p:Publishing_House)-[r]-(b)--(a:Author) 
            WHERE tolower(a.name) CONTAINS tolower($name) AND tolower(a.surname) CONTAINS tolower($surname) WITH
            collect(distinct(a{.*, born: toString(a.born)})) as authors, 
            collect(distinct(p{publishing_house:p.name, release_date:toString(r.release_date) })) as published, b
            OPTIONAL MATCH (b)-[r1:RATED]-(u:User) WITH b,r1,u, authors, published
            OPTIONAL MATCH (b)-[r2:RATED]-(a2:Anonymus) WITH [r1]+ [r2] as ratings, b, authors, published
            UNWIND  ratings as rates WITH DISTINCT rates as  ratings, b, authors, published
            WITH b, avg(ratings.rating) as a, authors, published """ + sort + "RETURN b{.*, average_rating:a},authors, published "
        books = session.execute_read(get_books, query, data)
    response = {'books': books}
    return jsonify(response)

def get_books_rating(tx, sort):
    query = """MATCH (b:Book) WITH b 
            MATCH (p:Publishing_House)-[r]-(b)--(a:Author) 
            WITH collect(distinct(a{.*, born: toString(a.born)})) as authors, 
            collect(distinct(p{publishing_house:p.name, release_date:toString(r.release_date) })) as published, b

            OPTIONAL MATCH (b)-[r1:RATED]-(u:User) WITH b,r1,u, authors, published
            OPTIONAL MATCH (b)-[r2:RATED]-(a2:Anonymus) WITH [r1]+ [r2] as ratings, b, authors, published
            UNWIND  ratings as rates 
            WITH DISTINCT rates as  ratings, b, authors, published

            OPTIONAL MATCH (b)-[c1:COMMENTED_ON]-(u:User) WITH b,c1,u, authors, published, ratings
            OPTIONAL MATCH (b)-[c2:COMMENTED_ON]-(a2:Anonymus) WITH [c1]+ [c2] as comments, b, authors, published, ratings
            UNWIND  comments as c
            WITH DISTINCT c as comments, b, authors, published, ratings

            OPTIONAL MATCH (b)-[r:RESERVATION]-(u:User) WITH b,r,u, authors, published, ratings, comments
            WITH DISTINCT r as reservations, b, authors, published, ratings, comments

            WITH b, avg(ratings.rating) as a, authors, published, count(comments) as c, count(reservations) as r 
            """ + sort + "RETURN b{.*, average_rating:a, comments:c, reservations:r},authors, published LIMIT 10"
    results = tx.run(query).data()
    books = [parse_book(result) for result in results]
    return books

@app.route('/ranking/books/rating', methods=['GET'])
def ranking_books_highest_rating_route():
    sort = "ORDER BY a IS NOT NULL DESC "
    with driver.session() as session:
        return session.execute_read(get_books_rating, sort)

@app.route('/ranking/books/comments', methods=['GET'])
def ranking_books_most_commented_route():
    sort = "ORDER BY c "
    with driver.session() as session:
        return session.execute_read(get_books_rating, sort)

@app.route('/ranking/books/borrowed', methods=['GET'])
def ranking_books_most_borrowed_route():
    sort = "ORDER BY r "
    with driver.session() as session:
        return session.execute_read(get_books_rating, sort)
    

def get_authors_rating(tx, sort):
    query = """
        MATCH(a:Author) WITH a MATCH (a)--(b:Book) WITH a, b
        OPTIONAL MATCH (b)-[r1:RATED]-(u:User) WITH b,r1,u, a
        OPTIONAL MATCH (b)-[r2:RATED]-(a2:Anonymus) WITH [r1]+ [r2] as ratings, b, a
        UNWIND  ratings as rates 
        WITH DISTINCT rates as  ratings, b, a
        OPTIONAL MATCH (b)-[c1:COMMENTED_ON]-(u:User) WITH b,c1,u, a, ratings
        OPTIONAL MATCH (b)-[c2:COMMENTED_ON]-(a2:Anonymus) WITH [c1]+ [c2] as comments, b, a, ratings
        UNWIND  comments as c
        WITH DISTINCT c as comments, b, a, ratings
        OPTIONAL MATCH (b)-[r:RESERVATION]-(u:User) WITH b,r,u,a, ratings, comments
        WITH DISTINCT r as reservations, b, a as author, ratings, comments

        WITH b, avg(ratings.rating) as a, author, count(comments) as c, count(reservations) as r 
        WITH b{title:b.title, average_rating:a, comments:c, reservations:r} as book, author

        WITH author, count(book) as b, collect(book) as books
        WITH author, books,  b"""+ sort + """
        RETURN author{.*, books:b, born: toString(born)} LIMIT 10""" 
    results = tx.run(query).data()
    #books = [(result) for result in results]
    return results

@app.route('/ranking/authors/numbooks', methods=['GET'])
def ranking_authors_number_of_books_route():
    sort = "ORDER by b DESC"
    with driver.session() as session:
        return session.execute_read(get_authors_rating, sort)
    
def get_book(tx, query, id):
    err = check_if_book_exists(tx, id)
    if err:
        return err
    results = tx.run(query, id=id).data()
    book = [parse_book(result) for result in results]
    return book[0]

@app.route('/book/<int:id>', methods=['GET'])
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
    return book


def edit_book(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(id)
    if err:
        return err
    query = """MATCH (b:Book) WHERE ID(b) = $id 
    SET b.title=$title, b.cover_photo=$cover_photo, b.genres=$genres, b.description=$description, b.number=$number
    CREATE (b:Book {title: $title, cover_photo: $cover_photo, genres:$genres, description:$description, number:$number})
    RETURN ID(b) as id"""
    result = tx.run(query, id=id,title=data["title"], cover_photo=data["cover_photo"],
        genres=data["genres"], description=data["description"], number=data["number"]).data()
    return jsonify({"Book edddited under id":result}), 200

@app.route('/book/<int:id>', methods=['PUT'])
def edit_book_route(id):
    needed_values=["login","password", "title", "genres", "description", "number"]
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    json_dict = request.get_json(force=True)
    cover_photo = (request.json["cover_photo"] if "cover_photo" in json_dict else "")
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["cover_photo"] = cover_photo
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(edit_book, data, id)


def delete_book(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(id)
    if err:
        return err
    query = """MATCH (b:Book) WHERE ID(b) = $id WITH b DETACH DELETE b"""
    result = tx.run(query, id=id).data()
    return jsonify({"Book deleted under id":id}), 200

@app.route('/book/<int:id>', methods=['DELETE'])
def delete_book_route(id):
    needed_values = ["login","password"]
    return initiate_request_with_id(needed_values, request, delete_book, id)

def add_comment(tx, login, password, comment, book_id):
    err = check_credentials(tx, login, password)
    if err:
        return err
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
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
    err = no_json_error_message(request)
    if err:
        return err
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
        
def edit_comment(tx, data, comment_id):
    err = check_credentials(data["login"], data["password"])
    if err:
        return err
    query = """MATCH (u:User {login: $login})-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id 
            RETURN c.comment as comment, ID(c) as id, u.login as login"""
    result = tx.run(query, login=data["login"], id=comment_id).data()
    if not result:
        return jsonify({"Message":"Comment doesn't exist"}), 404
    query = """MATCH (u:User {login: $login})-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id
            SET c.comment=$comment
            RETURN c.comment as comment, ID(c) as id, u.login as login"""
    result = tx.run(query, login=data["login"], id=comment_id, comment=data["comment"]).data()
    return result[0]

def edit_comment_admin(tx, data, comment_id):
    err = check_admin_credentials(data["login"], data["password"])
    if err:
        return err
    query = """MATCH (n)-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id 
            RETURN c.comment as comment, ID(c) as id"""
    result = tx.run(query, id=comment_id).data()
    if not result:
        return jsonify({"Message":"Comment doesn't exist"}), 404
    query = """MATCH (n)-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id
            SET c.comment=$comment
            RETURN c.comment as comment, ID(c) as id"""
    result = tx.run(query, id=comment_id, comment=data["comment"]).data()
    return result[0]

@app.route('/book/<int:id>/comment/<int:comment_id>', methods=['PUT'])
def edit_comment_route(id, comment_id):
    needed_values=["login","password","comment"]
    return initiate_request_with_id(needed_values, request, edit_comment, comment_id)

@app.route('/admin/book/<int:id>/comment/<int:comment_id>', methods=['PUT'])
def edit_comment_admin_route(id, comment_id):
    needed_values=["login","password","comment"]
    return initiate_request_with_id(needed_values, request, edit_comment_admin, comment_id)

def delete_comment(tx, data, comment_id):
    err = check_credentials(data["login"], data["password"])
    if err:
        return err
    query = """MATCH (u:User {login: $login})-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id 
            RETURN c.comment as comment, ID(c) as id, u.login as login"""
    result = tx.run(query, login=data["login"], id=comment_id).data()
    if not result:
        return jsonify({"Message":"Comment doesn't exist"}), 404
    query = """MATCH (u:User {login: $login})-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id DELETE c"""
    result = tx.run(query, login=data["login"], id=comment_id).data()
    return jsonify({"Message":"Comment deleted"}), 200

def delete_comment_admin(tx, data, comment_id):
    err = check_admin_credentials(data["login"], data["password"])
    if err:
        return err
    query = """MATCH (n)-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id 
            RETURN c.comment as comment, ID(c) as id"""
    result = tx.run(query, id=comment_id).data()
    if not result:
        return jsonify({"Message":"Comment doesn't exist"}), 404
    query = """MATCH (n)-[c:COMMENTED_ON]-(:Book) WHERE ID(c)=$id DELETE c"""
    result = tx.run(query, id=comment_id).data()
    return jsonify({"Message":"Comment deleted"}), 200

    
@app.route('/book/<int:id>/comment/<int:comment_id>', methods=['DELETE'])
def delete_comment_route(id, comment_id):    
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, delete_comment, comment_id)

@app.route('/admin/book/<int:id>/comment/<int:comment_id>', methods=['DELETE'])
def delete_comment_admin_route(id, comment_id):    
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, delete_comment_admin, comment_id)


def add_rating(tx, login, password, rating, book_id):
    err = check_credentials(tx, login, password)
    if err:
        return err
    err = check_if_book_exists(tx, book_id)
    if err:
        return err
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
    err = no_json_error_message(request)
    if err:
        return err
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

@app.route('/admin', methods=['GET', 'POST'])
def handle_admin_route():
    if request.method == 'POST':
        return add_admin_route()

def add_admin(tx, login, password):
    query = "MATCH (a:Admin) WHERE a.login=$login  RETURN a"
    result = tx.run(query, login=login).data()
    if result:
        response = {'message': 'Admin already exists'}
        return jsonify(response), 404
    else:
        query = "CREATE (a:Admin {login: $login, password:$password}) RETURN a, ID(a) as id"
        passw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('ascii')
        result = tx.run(query, login=login, password = passw).data()
        return parse_person(result[0], "a")
        
def add_admin_route():
    err = initiate_request_error_message(request, ["login","password"])
    if err:
        return err
    login = request.json['login']
    password = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(add_admin, login, password)


def edit_admin(tx, data):
    login = data["login"]
    err = check_admin_credentials(login, data["password"])
    if err:
        return err
    password = data["new_pass"]
    query = "MATCH (a:Admin {login: $login}) SET a.password=$password RETURN a, ID(a) as id"
    passw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('ascii')
    result = tx.run(query, login=login, password = passw).data()
    return parse_person(result[0], "a")

@app.route('/users', methods=['PUT'])        
def edit_admin_route():
    needed_values = ["login","password", "new_pass"]
    return initiate_request(needed_values, request, edit_admin)

def add_author(tx, data):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = "MATCH (a:Author {name:$name, surname: $surname}) RETURN a, ID(a) as id"
    result = tx.run(query, name=data["name"], surname=data["surname"]).data()
    if result:
        response = {'message': "Author %s %s aready exists" % (data["name"], data["surname"])}
        return jsonify(response), 404
    query = """CREATE (a:Author {name:$name, surname:$surname, born:date($born)}) RETURN ID(a) as id"""
    result = tx.run(query, name=data["name"], surname=data["surname"], born=data["born"]).data()
    return jsonify({"Author added under id":result}), 200

@app.route('/author', methods=[ 'POST'])
def add_author_route():
    needed_values=["login","password", "name", "surname", "born"]
    return initiate_request(needed_values, request, add_author)


def add_publishing_house(tx, data):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = "MATCH (p:Publishing_House {name:$name}) RETURN p, ID(p) as id"
    result = tx.run(query, name=data["name"]).data()
    if result:
        response = {'message': "Publishing House %s already exists" % (data["name"])}
        return jsonify(response), 404
    query = """CREATE (p:Publishing_House {name:$name}) RETURN p{.*, id:ID(p)} as `publishing house`"""
    result = tx.run(query, name=data["name"]).data()
    return result[0]

@app.route('/publishing_house', methods=[ 'POST'])
def add_publishing_house_route():
    needed_values=["login","password", "name"]
    return initiate_request(needed_values, request, add_publishing_house)


def get_publishing_house(tx, id):
    query = "MATCH (p:Publishing_House) WHERE ID(p)=$id RETURN p{.*, id:ID(p)} as `publishing house`"
    result = tx.run(query, id=id).data()
    if not result:
        response = {'message': "Publishing House under id %d doesn't exists in database" % (id)}
        return jsonify(response), 404
    else:
        return result[0]

@app.route('/publishing_house/<int:id>', methods=['GET'])
def get_publishing_house_route(id):
    with driver.session() as session:
        return session.execute_read(get_publishing_house, id)

def edit_publishing_house(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_publishing_house_exists(tx, id)
    if err:
        return err
    query = """MATCH (p:Publishing_House) WHERE ID(p)=$id SET p.name=$name RETURN p{.*, id:ID(p)} as `publishing house`"""
    result = tx.run(query, id=id, name=data["name"]).data()
    return result[0]

@app.route('/publishing_house/<int:id>', methods=['PUT'])
def edit_publishing_house_route(id):
    needed_values=["login","password", "name"]
    return initiate_request_with_id(needed_values, request, edit_publishing_house, id)


def delete_publishing_house(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_publishing_house_exists(tx, id)
    if err:
        return err
    query = "MATCH (p:Publishing_House)-[r]-(n) WHERE ID(p)=$id RETURN r"
    result = tx.run(query, id=id).data()
    if result:
        response = {'message': "You can't delete Publishing House that already has books" % (id)}
        return jsonify(response), 404
    query = "DELETE (p:Publishing_House) WHERE ID(p)=$id"
    result = tx.run(query, id=id).data()
    return jsonify({"message":"Publishing House deleted"}), 200

@app.route('/publishing_house/<int:id>', methods=['DELETE'])
def delete_publishing_house_route(id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, delete_publishing_house, id)


def get_author(tx, id):
    query = "MATCH (a:Author) WHERE ID(a)=$id RETURN a{.*, id:ID(a), born:toString(a.born)} as author"
    result = tx.run(query, id=id).data()
    if not result:
        response = {'message': "Author under id %d doesn't exists in database" % (id)}
        return jsonify(response), 404
    else:
        return result[0]

@app.route('/author/<int:id>', methods=['GET'])
def get_author_route(id):
    with driver.session() as session:
        return session.execute_read(get_author, id)

def edit_author(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_author_exists(tx, id)
    if err:
        return err
    query = """MATCH (a:Author) WHERE ID(a)=$id SET a.name=$name, a.surname=$surname, a.born=date($born) RETURN a{.*, id:ID(a), born:toString(a.born)} as author`"""
    result = tx.run(query, id=id, name=data["name"], surname=data["surname"], born=data["born"]).data()
    return result[0]

@app.route('/author/<int:id>', methods=['PUT'])
def edit_author_route(id):
    needed_values=["login","password", "name", "surname", "born"]
    return initiate_request_with_id(needed_values, request, edit_author, id)


def delete_author(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_author_exists(tx, id)
    if err:
        return err
    query = "MATCH (a:Author)-[r]-(n) WHERE ID(a)=$id RETURN r"
    result = tx.run(query, id=id).data()
    if result:
        response = {'message': "You can't delete author that already has books" % (id)}
        return jsonify(response), 404
    query = "DELETE (a:Author) WHERE ID(a)=$id"
    result = tx.run(query, id=id).data()
    return jsonify({"message":"Author deleted"}), 200

@app.route('/author/<int:id>', methods=['DELETE'])
def delete_author_route(id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, delete_author, id)

    
def add_book_author(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(tx,id)
    if err:
        return err
    err = check_if_author_exists(tx, id)
    if err:
        return err
    query = "MATCH (a:Author)-[r:WRITTEN_BY]-(b:Book) WHERE ID(a)=$author_id AND ID(b)=$id RETURN r"
    result = tx.run(query, author_id=data["author_id"], id=id).data()
    if result:
        response = {'message': "Author under id %d already has connection to book under id %d in database" % (data["author_id"], id)}
        return jsonify(response), 404
    query = "CREATE (a:Author)<-[:WRITTEN_BY]-(b:Book) WHERE ID(a)=$author_id AND ID(b)=$id RETURN r"
    result = tx.run(query, author_id=data["author_id"], id=id).data()
    if result:
        response = {'message': "Author under id %d assigned to book under id %d " % (data["author_id"], id)}
        return jsonify(response), 200

@app.route('/book/<int:id>/author', methods=['POST'])
def add_book_author_route(id):
    needed_values=["login","password", "author_id"]
    return initiate_request_with_id(needed_values, request, add_book_author, id)


def delete_book_author(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(tx,id)
    if err:
        return err
    err = check_if_author_exists(tx, data["author_id"])
    if err:
        return err
    query = "MATCH (a:Author)-[r:WRITTEN_BY]-(b:Book) WHERE ID(a)=$author_id AND ID(b)=$id RETURN r"
    result = tx.run(query, author_id=data["author_id"], id=id).data()
    if not result:
        response = {'message': "Author under id %d doesn't have connection to book under id %d in database" % (data["author_id"], id)}
        return jsonify(response), 404
    query = "MATCH (a:Author)<-[r:WRITTEN_BY]-(b:Book) WHERE ID(a)=$author_id AND ID(b)=$id DELETE r"
    result = tx.run(query, author_id=data["author_id"], id=id).data()
    response = {'message': "Author under id %d unassined from book under id %d " % (data["author_id"], id)}
    return jsonify(response), 200

@app.route('/book/<int:id>/author', methods=['DELETE'])
def delete_book_author_route(id):
    needed_values=["login","password", "author_id"]
    return initiate_request_with_id(needed_values, request, delete_book_author, id)


def add_book_publishing_house(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(tx,id)
    if err:
        return err
    err = check_if_publishing_house_exists(tx, data["publishing_house_id"])
    if err:
        return err
    query = "MATCH (p:Publishing_House)-[:RELEASED_BY {release_date:date($release_date)}]-(b:Book) WHERE ID(p)=$publishing_house_id AND ID(b)=$id RETURN r"
    result = tx.run(query, publishing_house_id=data["publishing_house_id"], id=id, release_date=data["release_date"]).data()
    if result:
        response = {'message': "Publishing House under id %d and realease date %s already has connection to book under id %d in database" % (data["publishing_house_id"], data["release_date"], id)}
        return jsonify(response), 404
    query = "CREATE (p:Publishing_House)<-[:RELEASED_BY {release_date:date($release_date)}]-(b:Book) WHERE ID(p)=$publishing_house_id AND ID(b)=$id"
    result = tx.run(query, publishing_house_id=data["publishing_house_id"], id=id, release_date=data["release_date"]).data()
    response = {'message': "Publishing House under id %d and realease date %s assined to book under id %d " % (data["publishing_house_id"], data["release_date"], id)}
    return jsonify(response), 200

@app.route('/book/<int:id>/publishing_house', methods=['POST'])
def add_book_publishing_house_route(id):
    needed_values=["login","password", "publishing_house_id", "release_date"]
    return initiate_request_with_id(needed_values, request, add_book_publishing_house, id)


def delete_book_publishing_house(tx, data, id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(tx,id)
    if err:
        return err
    err = check_if_publishing_house_exists(tx, data["publishing_house_id"])
    if err:
        return err
    query = "MATCH (p:Publishing_House)-[:RELEASED_BY {release_date:date($release_date)}]-(b:Book) WHERE ID(p)=$publishing_house_id AND ID(b)=$id RETURN r"
    result = tx.run(query, publishing_house_id=data["publishing_house_id"], id=id, release_date=data["release_date"]).data()
    if not result:
        response = {'message': "Publishing House under id %d and realease date %s doesn't have connection to book under id %d in database" % (data["publishing_house_id"], data["release_date"], id)}
        return jsonify(response), 404
    query = "MATCH (p:Publishing_House)<-[:RELEASED_BY {release_date:date($release_date)}]-(b:Book) WHERE ID(p)=$publishing_house_id AND ID(b)=$id DELETE r"
    result = tx.run(query, publishing_house_id=data["publishing_house_id"], id=id, release_date=data["release_date"]).data()
    response = {'message': "Publishing House under id %d and realease date %s unassined from book under id %d " % (data["publishing_house_id"], data["release_date"], id)}
    return jsonify(response), 200

@app.route('/book/<int:id>/publishing_house', methods=['DELETE'])
def delete_book_publishing_house_route(id):
    needed_values=["login","password", "publishing_house_id", "release_date"]
    return initiate_request_with_id(needed_values, request, delete_book_publishing_house, id)

def make_reservation(tx, data, id):
    err = check_credentials(tx, data["login"], data["password"])
    if err:
        return err
    err = check_if_book_exists(tx, id)
    if err:
        return err
    # check if no other *active* reservations on the same book from the same user
    query = "MATCH (u:User)-[r:RESERVATION]-(b:Book) WHERE u.login = $login AND ID(b) = $id AND r.active = True RETURN r"
    result = tx.run(query, login=data["login"], id=id).data()
    if result:
        response = {'message': "You have either reserved or borrowed this book already. Finish previous reservation process before starting new one." }
        return jsonify(response), 403
    # add reservation
    query = """MATCH (u:User) WHERE u.login = $login WITH u MATCH (b:Book) WHERE ID(b) = $id  
        CREATE (u)-[:RESERVATION { status:"unconfirmed", date_of_collection:Null, 
        return_deadline:Null, date_of_return:Null, active:True, waiting_list: Null }]->(b)"""
    result = tx.run(query, login=data["login"], id=id).data()
    response = {'message': "Book reservation process initialized. Confirm to proceed"}
    return jsonify(response), 200


@app.route('/book/<int:id>/reserve', methods=['POST'])
def make_reservation_route(id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, make_reservation, id)

def get_reservation_history(tx, data, id):
    err = check_credentials(tx, data["login"], data["password"])
    if err:
        err = check_admin_credentials(tx, data["login"], data["password"])
        if err:
            return err
    query = ""
    if data["active"]:
        query = "" # get all active reservations from user sorted by date
    else:
        query = "" # get all reservations from user sorted by date
    result = tx.run(query, id=id).data()
    response = {'message': "Book reservation process initialized. Confirm to proceed"}
    return jsonify(response), 200

@app.route('/user/<int:id>/reservation_history', methods=['GET'])
def get_reservation_history_route(id):
    needed_values=["login","password", "active"]
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_read(get_reservation_history, data, id)


def cancel_reservation_user(tx, data, id, reservation_id):
    err = check_credentials(tx, data["login"], data["password"])
    if err:
        return err
    # check if login and id come from the same person
    query = "MATCH (u:User) WHERE u.login = $login AND ID(u) = $id RETURN u"
    result = tx.run(query, login=data["login"], id=id).data()
    if not result:
        response = {'message': "You have to rights to cancel this reservation" }
        return jsonify(response), 403
    # check if reservation exists
    query = """MATCH (u:User)-[r:RESERVATION]-(:Book) WHERE ID(u) = $id_u AND ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query, id_u=id, id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    print(result[0]["status"])
    # check if it has unconfirmed status
    if result[0]["status"] != "unconfirmed":
        response = {'message': "You can only cancel unconfirmed reservations" }
        return jsonify(response), 404
    # cancel reservation
    query = """MATCH (u:User)-[r:RESERVATION]-(:Book) WHERE ID(u) = $id_u AND ID(r)= $id_r SET r.status = "canceled", r.active = False """
    result = tx.run(query, id_u=id, id_r=reservation_id).data()
    response = {'message': "Reservation canceled" }
    return jsonify(response), 200
       
@app.route('/user/<int:id>/reservation/<int:reservation_id>/cancel', methods=['DELETE'])
def cancel_reservation_user_route(id, reservation_id):
    needed_values=["login","password"]
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(cancel_reservation_user, data, id, reservation_id)
    

def cancel_reservation_admin(tx, data, reservation_id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query,  id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    # check if it has either "On waiting list" status or "ready for collection" status
    if not(result[0]["status"] == "unconfirmed" or result[0]["status"] == "on waiting list" or result[0]["status"] == "ready for collection"):
        response = {'message': "You can only cancel reservations that hadn't been recieved yet or canceled" }
        return jsonify(response), 404
    # cancel reservation
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r SET r.status = "canceled", r.active = False """
    result = tx.run(query,  id_r=reservation_id).data()
    response = {'message': "Reservation canceled" }
    return jsonify(response), 200
    

@app.route('/reservation/<int:reservation_id>/cancel', methods=['DELETE'])
def cancel_reservation_admin_route(reservation_id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, cancel_reservation_admin, reservation_id)
    

def confirm_reservation(tx, data, id, reservation_id):
    err = check_credentials(tx, data["login"], data["password"])
    if err:
        return err
    # check if login and id come from the same person
    query = "MATCH (u:User) WHERE u.login = $login AND ID(u) = $id RETURN u"
    result = tx.run(query, login=data["login"], id=id).data()
    if not result:
        response = {'message': "You have to rights to confirm this reservation" }
        return jsonify(response), 403
    # check if reservation exists
    query = """MATCH (u:User)-[r:RESERVATION]-(:Book) WHERE ID(u) = $id_u AND ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query, id_u=id, id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    print(result[0]["status"])
    # check if it has unconfirmed status
    if result[0]["status"] != "unconfirmed":
        response = {'message': "You can only confirm unconfirmed reservations" }
        return jsonify(response), 404
    # confirm reservation
    query = """MATCH (u:User)-[r:RESERVATION]-(:Book) WHERE ID(u) = $id_u AND ID(r)= $id_r SET r.status = "ready for collection" """
    result = tx.run(query, id_u=id, id_r=reservation_id).data()
    response = {'message': "Reservation confirmed" }
    return jsonify(response), 200

@app.route('/user/<int:id>/reservation/<int:reservation_id>/confirm', methods=['PUT'])
def confirm_reservation_user_route(id, reservation_id):
    needed_values=["login","password"]
    err = initiate_request_error_message(request, needed_values)
    if err:
        return err
    data = {x:request.json[x] for x in needed_values if x!="password"}
    data["password"] = request.json['password'].encode('ascii')
    with driver.session() as session:
        return session.execute_write(confirm_reservation, data, id, reservation_id)
    


def recieve_reservation(tx, data, reservation_id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query,  id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    # check if it has "ready for collection" status
    if not(result[0]["status"] == "ready for collection"):
        response = {'message': "You can only give books that are in the library to users" }
        return jsonify(response), 404
    # give book to user
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)=$id_r
    WITH r, apoc.date.currentTimestamp() AS presentInMs
    WITH r, apoc.date.add(presentInMs, "ms", 30, "day") AS deadlineInMs, presentInMs
    WITH r, datetime({epochMillis: presentInMs}) as rec, datetime({epochMillis: deadlineInMs}) AS deadline
    SET r.status = "recieved" SET r.date_of_collection = rec SET r.return_deadline = deadline """
    result = tx.run(query,  id_r=reservation_id).data()
    response = {'message': "Book collected" }
    return jsonify(response), 200

@app.route('/reservation/<int:reservation_id>/recieve', methods=['PUT'])
def recieve_reservation_route(reservation_id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, recieve_reservation, reservation_id)
    

def prolong_reservation(tx, data, reservation_id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query,  id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    # check if it has "ready for collection" status
    if not(result[0]["status"] == "recieved"):
        response = {'message': "You can only prolong recieved books" }
        return jsonify(response), 404
    # prolong book
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r
    WITH r, apoc.date.currentTimestamp() AS presentInMs
    WITH r, apoc.date.add(presentInMs, "ms", 30, "day") AS deadlineInMs
    WITH r, datetime({epochMillis: deadlineInMs}) AS deadline
    SET r.status = "prolonged", r.return_deadline = deadline """
    result = tx.run(query,  id_r=reservation_id).data()
    response = {'message': "Book collected" }
    return jsonify(response), 200

@app.route('/reservation/<int:reservation_id>/prolong', methods=['PUT'])
def prolong_reservation_route(reservation_id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, prolong_reservation, reservation_id)   


def return_reservation(tx, data, reservation_id):
    err = check_admin_credentials(tx, data["login"], data["password"])
    if err:
        return err
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r RETURN r.status as status"""
    result = tx.run(query,  id_r=reservation_id).data()
    if not result:
        response = {'message': "Reservation uder id %d doesn't exist" %(reservation_id) }
        return jsonify(response), 404
    # check if it has "ready for collection" status
    if not(result[0]["status"] == "recieved" or result[0]["status"] == "prolonged" ):
        response = {'message': "You can only return books that are with the user" }
        return jsonify(response), 404
    # prolong book
    query = """MATCH (:User)-[r:RESERVATION]-(:Book) WHERE ID(r)= $id_r
    WITH r, apoc.date.currentTimestamp() AS presentInMs
    WITH r, datetime({epochMillis: presentInMs}) AS pres
    SET r.status = "returned", r.date_of_return = pres, r.active = False"""
    result = tx.run(query,  id_r=reservation_id).data()
    response = {'message': "Book collected" }
    return jsonify(response), 200

@app.route('/reservation/<int:reservation_id>/return', methods=['PUT'])
def return_reservation_route(reservation_id):
    needed_values=["login","password"]
    return initiate_request_with_id(needed_values, request, return_reservation, reservation_id)

if __name__ == '__main__':
    app.run()