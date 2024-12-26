import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, jsonify
from functools import wraps
from flask_cors import CORS
import jwt
import datetime
from dotenv import load_dotenv
import os
import json

load_dotenv()

firebase_config_json = os.getenv("FIREBASE_CONFIG")

if not firebase_config_json:
    raise ValueError("Firebase configuration is not set in the environment variables")

# Parse the JSON string to a dictionary
firebase_config = json.loads(firebase_config_json)

cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)

# Get a reference to the Firestore database
db = firestore.client()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = 'your_jwt_secret_key'

# Route to render the home page
@app.route('/')
def home():
    return render_template('index.html')

# Route to handle login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()  # Get JSON data from the request
    
    email = data.get('email')
    password = data.get('password')

    # Query Firestore to find the user by email
    user_ref = db.collection('users').document(email)
    user_doc = user_ref.get()

    

    if user_doc.exists:
        user = user_doc.to_dict()
        if user['password'] == password:
            token = jwt.encode({
                'email': user['email'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expiration time
            }, app.config['SECRET_KEY'], algorithm='HS256')

            return jsonify({"message": "Login successful", "token": token}), 200
        else:
            return jsonify({"error": "Invalid password"}), 401
    else:
        return jsonify({"error": "User not found"}), 404

# Route to handle signup
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()  

    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    password = data.get('password')
    address = data.get('address')

    if not all([name, phone, email, password, address]):
        return jsonify({"message": "All fields are required"}), 400

    # Check if the user already exists in Firestore
    user_ref = db.collection('users').document(email)
    user_doc = user_ref.get()
    if user_doc.exists:
        return jsonify({"error": "User already exists"}), 400

    # Create a new user document in Firestore
    user = {
        "name": name,
        "phone": phone,
        "email": email,
        "password": password,  # In a real app, password should be hashed!
        "address": address
    }

    # Add the new user to Firestore
    user_ref.set(user)

    # Respond with a success message
    return jsonify({"message": "Signup successful!"}), 201

@app.route('/contact', methods=['POST'])
def submit_contact():
    try:
        # Get data from the request
        form_data = request.get_json()

        first_name = form_data.get('firstName')
        last_name = form_data.get('lastName')
        email = form_data.get('email')
        phone = form_data.get('phone')
        message = form_data.get('message')

        # Check if the data is valid
        if not all([first_name, last_name, email, phone, message]):
            return jsonify({"error": "All fields are required!"}), 400

        # Store data in Firestore
        contact_ref = db.collection('contact').document()
        contact_ref.set({
            'firstName': first_name,
            'lastName': last_name,
            'email': email,
            'phone': phone,
            'message': message
        })

        return jsonify({"success": "Contact form submitted successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/getplots', methods=['GET'])
def get_plots():
    # Get region from query parameters
    print("detected")
    region = request.args.get('region')
    if not region:
        return jsonify({"error": "Region parameter is required"}), 400

    # Query Firebase for plots in the specified region
    try:
        plots_ref = db.collection('plots')  # Replace 'plots' with your Firebase collection name
        query = plots_ref.where('region', '==', region).stream()

        plots = []
        for doc in query:
            plots.append(doc.to_dict())

        if not plots:
            return jsonify({"message": f"No plots found in region: {region}"}), 404

        return jsonify(plots), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/getproperties',methods=['GET'])
def get_properties():
    try:
        plots_ref=db.collection('plots')
        query = plots_ref.stream()
        plots = []
        for doc in query:
            plots.append(doc.to_dict())

        if not plots:
            return jsonify({"message"}), 404

        return jsonify(plots), 200

    except Exception as e:
        return jsonify(str(e)),500

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 403

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = {"email": data['email']}  # Assuming the JWT has 'user_email' in it
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 403

        return f(current_user, *args, **kwargs)

    return decorated_function

@app.route('/protected/user-details', methods=['GET'])
@token_required
def get_user_details(current_user):
    # Fetch user data from Firestore using the email
    user_ref = db.collection('users').document(current_user['email'])
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()  # This retrieves the Firestore document as a dictionary
        return jsonify({"user": user_data})
    else:
        return jsonify({'message': 'User not found!'}), 404


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))  # Default to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port)
