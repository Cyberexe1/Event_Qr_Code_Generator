from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import qrcode
from flask import Flask, render_template, request
import mysql.connector
import io
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Flask App and DB
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Vikas123@localhost/qr_registration_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Database model
class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    dob = db.Column(db.String(50))
    address = db.Column(db.Text)
    event = db.Column(db.String(100))
    ticketType = db.Column(db.String(50))
    price = db.Column(db.Float)
    dietary = db.Column(db.String(100))
    specialRequirements = db.Column(db.String(100))
    qr_image = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Generate QR code
def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, format="PNG")
    img_io.seek(0)
    return img_io

@app.route("/")
def serve_form():
    return send_from_directory('.', 'qrcode.html')

@app.route("/generate_qr", methods=["POST", "OPTIONS"])
def generate_qr():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response

    data = request.get_json()
    logger.debug(f"Received data: {data}")

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Save to DB
    record = Registration(
        name=data.get('name'),
        email=data.get('email'),
        phone=data.get('phone'),
        dob=data.get('dob'),
        address=data.get('address'),
        event=data.get('event'),
        ticketType=data.get('ticketType'),
        price=float(data.get('price', 0)),
        dietary=data.get('dietary'),
        specialRequirements=data.get('specialRequirements'),
    )
    db.session.add(record)
    db.session.commit()

    # Create QR with record ID
    view_url = f"http://localhost:5000/view_registration/{record.id}"  # change domain in prod
    qr_img_io = generate_qr_code(view_url)
    record.qr_image = qr_img_io.getvalue()
    db.session.commit()

    response = send_file(io.BytesIO(record.qr_image), mimetype="image/png")
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route("/view_registration/<int:id>")
def view_registration(id):
    record = Registration.query.get_or_404(id)
    return render_template("view.html", record=record)

@app.route('/scan')
def scan_qr():
    return render_template('view.html')

@app.route('/get_qr_data', methods=['POST', 'OPTIONS'])
def get_qr_data():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response
        
    try:
        data = request.get_json()
        qr_value = data.get('qr_value')
        
        if not qr_value:
            response = jsonify({"status": "error", "message": "No QR value provided"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400
        
        # Extract ID from QR URL (e.g., "http://localhost:5000/view_registration/123")
        if '/view_registration/' in qr_value:
            try:
                record_id = int(qr_value.split('/view_registration/')[-1])
                record = Registration.query.get(record_id)
                
                if record:
                    response = jsonify({
                        "status": "success",
                        "data": {
                            "id": record.id,
                            "name": record.name,
                            "email": record.email,
                            "phone": record.phone,
                            "dob": record.dob,
                            "address": record.address,
                            "event": record.event,
                            "ticketType": record.ticketType,
                            "price": record.price,
                            "dietary": record.dietary,
                            "specialRequirements": record.specialRequirements,
                            "created_at": record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else None
                        }
                    })
                    response.headers.add("Access-Control-Allow-Origin", "*")
                    return response
                else:
                    response = jsonify({"status": "error", "message": "No registration found for this QR code"})
                    response.headers.add("Access-Control-Allow-Origin", "*")
                    return response
            except (ValueError, IndexError):
                response = jsonify({"status": "error", "message": "Invalid QR code format"})
                response.headers.add("Access-Control-Allow-Origin", "*")
                return response
        else:
            response = jsonify({"status": "error", "message": "QR code does not contain a valid registration URL"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
            
    except Exception as e:
        logger.error(f"Error in get_qr_data: {str(e)}")
        response = jsonify({"status": "error", "message": "Internal server error"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@app.route('/show_result/<data>')
def show_result(data):
    # Connect to your MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vikas123",
        database="qr_registration_db"
    )
    cursor = conn.cursor(dictionary=True)

    # Search QR data in DB
    cursor.execute("SELECT * FROM registration WHERE registration = %s", (data,))
    record = cursor.fetchone()

    cursor.close()
    conn.close()

    if record:
        return f"QR Code Found: {record}"
    else:
        return "No matching record found."

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
