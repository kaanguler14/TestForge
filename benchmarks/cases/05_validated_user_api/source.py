from flask import Flask, jsonify, request

app = Flask(__name__)
users = []


@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'name' not in data or not isinstance(data['name'], str) or not data['name'].strip():
        return jsonify({"error": "valid name is required"}), 400
    if 'age' not in data or not isinstance(data['age'], int) or data['age'] < 0 or data['age'] > 150:
        return jsonify({"error": "valid age is required"}), 400
    user = {"id": len(users) + 1, "name": data['name'], "age": data['age']}
    users.append(user)
    return jsonify(user), 201
