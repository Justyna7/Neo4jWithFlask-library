from flask import Flask, jsonify, request, json
import bcrypt

def error_message(json_dict, values):
    for x in values:
        if x not in json_dict:
            response = {'message': x + ' not provided'}
            return jsonify(response), 404

def no_json_error_message(request):
    if request.data == b'':
        response = {'message': 'Content type should be application/json and request body should not be empty'}
        return jsonify(response), 404

def initiate_request_error_message(request, needed_values):
    err = no_json_error_message(request)
    if err:
        return err
    json_dict = request.get_json(force=True)
    # needed_values=["login","password"]
    err = error_message(json_dict, needed_values)
    if err:
        return err

def check_credentials(tx, login, password):
    query = "MATCH (u:User) WHERE u.login=$login RETURN u, ID(u) as id"
    user = tx.run(query, login=login).data()
    if not user:
        response = {'message': "User doesn't exists"}
        return jsonify(response), 404
    if not bcrypt.checkpw(password, user[0]['u']['password'].encode('ascii')):
        response = {'message': "Wrong password"}
        return jsonify(response), 401

def check_admin_credentials(tx, login, password):
    query = "MATCH (a:Admin) WHERE a.login=$login RETURN a, ID(a) as id"
    admin = tx.run(query, login=login).data()
    if not admin:
        response = {'message': "Admin doesn't exists"}
        return jsonify(response), 404
    if not bcrypt.checkpw(password, admin[0]['a']['password'].encode('ascii')):
        response = {'message': "Wrong password"}
        return jsonify(response), 401

def check_if_book_exists(tx, id):
    query = "MATCH (b:Book) WHERE ID(b)=$id RETURN b"
    book = tx.run(query, id=id).data()
    if not book:
        response = {'message': "Book doesn't exists"}
        return jsonify(response), 404