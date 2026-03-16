
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from emotion_ai import analyze_emotion
from ai_engine import generate_ai_reply
import matplotlib.pyplot as plt
import os
from datetime import datetime
from flask import flash # Make sure to import flash at the top of your file
import csv
from io import StringIO
from flask import Response
import random


# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
app.secret_key = "mindaura_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mindaura.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================
# DATABASE MODELS
# =========================

class Podcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_url = db.Column(db.String(500))  # Link or filename
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)



class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    college = db.Column(db.String(100))
    phone = db.Column(db.String(20), unique=True, nullable=False)



class EmotionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    emotion = db.Column(db.String(50))
    stress = db.Column(db.Integer)
    # ADD THIS LINE:
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Counselor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    education = db.Column(db.String(100))
    location = db.Column(db.String(100))
    profile_pic = db.Column(db.String(200), default="default.png")

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(100))
    location = db.Column(db.String(200))

class AIChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    sender = db.Column(db.String(10))  # 'user' or 'ai'
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ChatRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    counselor_id = db.Column(db.Integer, db.ForeignKey('counselor.id'))
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('chat_request.id'), nullable=False)
    sender_id = db.Column(db.Integer, nullable=False) # Store the ID of whoever sent it
    sender_type = db.Column(db.String(10)) # 'student' or 'counselor'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# CHART GENERATOR
# =========================
def generate_chart(student_id):
    logs = EmotionLog.query.filter_by(student_id=student_id).all()
    if not logs:
        return None
    stress_levels = [log.stress for log in logs]
    os.makedirs("static/images", exist_ok=True)
    path = f"static/images/chart_{student_id}.png"
    plt.figure(figsize=(5, 3))
    plt.plot(stress_levels)
    plt.xlabel("Entries")
    plt.ylabel("Stress Level")
    plt.title("Your Emotional Trend")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

# =========================
# RISK DETECTION
# =========================
def check_high_risk(student_id):
    logs = EmotionLog.query.filter_by(student_id=student_id)\
        .order_by(EmotionLog.id.desc()).limit(5).all()
    if len(logs) < 3:
        return False
    high_stress = sum(1 for log in logs if log.stress >= 4)
    return high_stress >= 3

# =========================
# ROUTES
# =========================
@app.route("/admin/download_students")
def download_students():
    if "admin_id" not in session: return redirect(url_for("admin_login"))
    
    students = Student.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Student ID', 'Full Name', 'Email', 'Phone', 'College'])
    for s in students:
        cw.writerow([s.id, s.name, s.email, s.college])
    
    response = Response(si.getvalue(), mimetype="text/csv")
    response.headers.set("Content-Disposition", "attachment", filename="students_report.csv")
    return response

@app.route("/admin_add_counselor", methods=["POST"])
def admin_add_counselor():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    education = request.form.get("education")
    
    # Simple check to see if counselor already exists
    existing = Counselor.query.filter_by(email=email).first()
    if existing:
        flash("Counselor with this email already exists!", "danger")
        return redirect(url_for("admin_dashboard"))

    # Hash password and save
    hashed_pw = generate_password_hash(password)
    new_counselor = Counselor(
        name=name, 
        email=email, 
        password=hashed_pw, 
        education=education
    )
    
    db.session.add(new_counselor)
    db.session.commit()
    
    flash("Counselor added successfully!", "success")
    return redirect(url_for("admin_dashboard")) 

@app.route("/admin/add_podcast", methods=["POST"])
def add_podcast():
    new_p = Podcast(
        title=request.form['title'],
        description=request.form['description'],
        video_url=request.form['video_url']
    )
    db.session.add(new_p)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_podcast/<int:id>")
def delete_podcast(id):
    p = Podcast.query.get(id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

# 3. Delete Counselor
@app.route("/admin/delete_counselor/<int:id>")
def delete_counselor(id):
    c = Counselor.query.get(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))





@app.route("/")
def home():
    # Fetch all notifications (events)
    notifications = Notification.query.order_by(Notification.date_posted.desc()).all()
    # Fetch all podcasts
    podcasts = Podcast.query.order_by(Podcast.date_posted.desc()).all()
    # Fetch the very latest event for the Popup
    latest_event = Notification.query.order_by(Notification.id.desc()).first()
    
    return render_template("home.html", 
                           notifications=notifications, 
                           podcasts=podcasts, 
                           latest_event=latest_event)

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    phone = data.get('phone')
    
    if not phone:
        return jsonify({"success": False, "message": "Phone number is required"})

    # 1. Generate a random 6-digit code
    otp = str(random.randint(100000, 999999))
    
    # 2. Store it in the session to verify later
    session['otp'] = otp
    
    # 3. PRINT TO TERMINAL (This is where you find the code!)
    print("\n" + "="*30)
    print(f"MOCK SMS SENT TO: {phone}")
    print(f"YOUR VERIFICATION CODE IS: {otp}")
    print("="*30 + "\n")

    return jsonify({"success": True})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # 1. Capture form data
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        college = request.form.get("college")
        password = request.form.get("password")
        user_otp = request.form.get("otp")
        
        # 2. Verify OTP from session
        stored_otp = session.get('otp')
        
        if not stored_otp or user_otp != stored_otp:
            flash("Invalid or expired OTP. Please check your terminal and try again.", "danger")
            return redirect(url_for("signup"))

        # 3. Hash password and create student object
        hashed_password = generate_password_hash(password)
        new_student = Student(
            name=name,
            email=email,
            phone=phone,
            college=college,
            password=hashed_password
        )
        
        # 4. Attempt to save to database
        try:
            db.session.add(new_student)
            db.session.commit()
            
            # 5. Cleanup: Remove OTP from session after successful registration
            session.pop('otp', None) 
            
            flash("Account created successfully! You can now login.", "success")
            return redirect(url_for("login"))
            
        except Exception as e:
            db.session.rollback()
            # This triggers if email or phone is already in the database
            flash("Registration failed. Email or Phone number might already be registered.", "danger")
            print(f"Database Error: {e}") # Debugging
            return redirect(url_for("signup"))
            
    # GET request returns the signup page
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Student.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["student_id"] = user.id
            return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/counselor_login", methods=["GET", "POST"])
def counselor_login():
    if request.method == "POST":
        counselor = Counselor.query.filter_by(email=request.form["email"]).first()
        if counselor and check_password_hash(counselor.password, request.form["password"]):
            session["counselor_id"] = counselor.id
            return redirect(url_for("counselor_dashboard"))
    return render_template("counselor_login.html")

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin = Admin.query.filter_by(email=request.form["email"]).first()
        if admin and check_password_hash(admin.password, request.form["password"]):
            session["admin_id"] = admin.id
            return redirect("/admin_dashboard")
    return render_template("admin_login.html")


@app.route("/counselor/student_profile/<int:student_id>")
def counselor_view_profile(student_id):
    if "counselor_id" not in session:
        return redirect(url_for("counselor_login"))
        
    student = Student.query.get_or_404(student_id)
    logs = EmotionLog.query.filter_by(student_id=student_id).order_by(EmotionLog.id.desc()).all()
    
    return render_template("student_detail_view.html", student=student, logs=logs)

# Accept Request
@app.route("/counselor/accept_chat/<int:request_id>")
def accept_chat(request_id):
    req = ChatRequest.query.get_or_404(request_id)
    req.status = 'accepted'
    db.session.commit()
    # Redirect to the chat room with this student
    return redirect(url_for('private_chat_room', request_id=req.id))
# Reject Request
@app.route("/counselor/reject_chat/<int:request_id>")
def reject_chat(request_id):
    req = ChatRequest.query.get_or_404(request_id)
    req.status = 'rejected'
    db.session.commit()
    return redirect(url_for('view_requests'))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "student_id" not in session:
        return redirect(url_for("login"))

    student = Student.query.get(session["student_id"])
    emotion = None 

    if request.method == "POST":
        text = request.form.get("text")
        if text:
            # Analyze emotion and stress
            emotion, stress = analyze_emotion(text)

            # Log to database
            log = EmotionLog(student_id=student.id, text=text, emotion=emotion, stress=stress)
            db.session.add(log)
            db.session.commit()

            # Handle Alerts
            if emotion == "Suicidal":
                flash("🚨 Urgent: We are concerned about your safety. Please reach out to a counselor.", "danger")
            elif emotion == "Depression":
                flash("It sounds like you're going through a tough time. We are here for you.", "warning")

            # Generate AI Reply
            response_text = generate_ai_reply(text, emotion)
            ai_log = AIChat(student_id=student.id, sender="ai", message=response_text)
            db.session.add(ai_log)
            db.session.commit()

    # --- FETCH DATA FOR SIDEBAR & UI ---
    ai_chats = AIChat.query.filter_by(student_id=student.id).all()
    counselors = Counselor.query.all()
    
    # IMPORTANT: This allows the "Accept Chat" card to appear
    chat_requests = ChatRequest.query.filter_by(student_id=student.id, status='pending').all()

    # Prepare Chart Data
    logs = EmotionLog.query.filter_by(student_id=student.id).order_by(EmotionLog.timestamp.asc()).all()
    chart_labels = [l.timestamp.strftime("%H:%M") for l in logs[-10:]]
    chart_data = [l.stress for l in logs[-10:]]
    current_mood = logs[-1].emotion if logs else "Neutral"

    return render_template(
        "student_dashboard.html",
        student=student,
        ai_chats=ai_chats,
        counselors=counselors,
        chat_requests=chat_requests,
        chart_labels=chart_labels,
        chart_data=chart_data,
        current_mood=current_mood,
        current_emotion=emotion 
    )

@app.route("/student/chat", methods=["POST"])
def student_chat():
    data = request.get_json()
    user_message = data.get("message")
    
    if not user_message:
        return jsonify({"reply": "No message received"}), 400

    try:
        # Passing 'Neutral' as a default emotion for testing
        ai_reply = generate_ai_reply(user_message, "Neutral")
        return jsonify({"reply": ai_reply})
    except Exception as e:
        print(f"ROUTE ERROR: {e}")
        return jsonify({"reply": "⚠️ The server had trouble talking to the AI."})



@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    
    # Fetch all data to display on the dashboard
    students = Student.query.all()
    counselors = Counselor.query.all()
    podcasts = Podcast.query.order_by(Podcast.date_posted.desc()).all()
    
    # Since you use the 'Notification' model for Live Events:
    events = Notification.query.order_by(Notification.date_posted.desc()).all()
    
    return render_template("admin_dashboard.html",
                           students=students,
                           counselors=counselors,
                           podcasts=podcasts,
                           events=events) # These names must match the {% for %} in HTML


@app.route("/send_private_msg", methods=["POST"])
def send_private_msg():
    data = request.get_json()
    # Determine who is sending based on session
    if "student_id" in session:
        s_id, s_type = session["student_id"], "student"
    elif "counselor_id" in session:
        s_id, s_type = session["counselor_id"], "counselor"
    else:
        return jsonify({"error": "Unauthorized"}), 401

    new_msg = PrivateMessage(
        request_id=data['request_id'],
        sender_id=s_id,
        sender_type=s_type,
        message=data['message']
    )
    db.session.add(new_msg)
    db.session.commit()
    return jsonify({"status": "sent"})


@app.route("/get_private_msgs/<int:request_id>")
def get_private_msgs(request_id):
    req = ChatRequest.query.get(request_id)
    msgs = PrivateMessage.query.filter_by(request_id=request_id).order_by(PrivateMessage.timestamp.asc()).all()
    
    output = []
    current_user_id = session.get("student_id") or session.get("counselor_id")
    current_user_type = "student" if "student_id" in session else "counselor"

    for m in msgs:
        output.append({
            "message": m.message,
            "side": "mine" if (m.sender_id == current_user_id and m.sender_type == current_user_type) else "theirs"
        })
    
    # Send BOTH the messages and the current status
    return jsonify({
        "messages": output,
        "status": req.status  # This tells the JS if the session is 'completed'
    })

@app.route("/counselor/end_session/<int:request_id>", methods=["POST"])
def end_session(request_id):
    if "counselor_id" not in session:
        return redirect(url_for("home"))
        
    req = ChatRequest.query.get_or_404(request_id)
    req.status = 'completed'
    db.session.commit()
    
    flash("Session ended successfully.", "success")
    return redirect(url_for("counselor_dashboard"))

    
@app.route("/add_live_event", methods=["POST"])
def add_live_event():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    
    # Capture everything from the form
    new_event = Notification(
        title=request.form["title"],
        description=request.form["description"],
        date_posted=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
        location=request.form.get("location", "Online"), # Capture Location
        time=request.form.get("time", "")                # Capture Time
    )
    db.session.add(new_event)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/counselor_dashboard")
def counselor_dashboard():
    if "counselor_id" not in session:
        return redirect(url_for("counselor_login"))

    counselor = Counselor.query.get(session["counselor_id"])
    
    # IMPROVED QUERY: Catching variations and high stress
    high_risk_logs = db.session.query(EmotionLog, Student).join(
        Student, EmotionLog.student_id == Student.id
    ).filter(
        (EmotionLog.emotion.ilike("%Suicidal%")) | 
        (EmotionLog.emotion.ilike("%Depression%")) |
        (EmotionLog.emotion.ilike("%Depressed%")) |
        (EmotionLog.stress >= 4)  # Alert counselors if stress is 4 or 5
    ).order_by(EmotionLog.timestamp.desc()).all()

    # The rest of your code remains the same...
    active_requests = ChatRequest.query.filter(
        ChatRequest.counselor_id == counselor.id,
        ChatRequest.status != 'completed'
    ).all()

    pending_count = ChatRequest.query.filter_by(
        counselor_id=counselor.id, 
        status='pending'
    ).count()

    students = Student.query.all()
    notifications = Notification.query.order_by(Notification.date_posted.desc()).all()

    return render_template(
        "counselor_dashboard.html",
        counselor=counselor,
        students=students,
        notifications=notifications,
        high_risk_logs=high_risk_logs,
        active_requests=active_requests,
        pending_count=pending_count
    )
@app.route("/counselor/clear_alerts", methods=["POST"])
def clear_high_risk_alerts():
    if "counselor_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # We "clear" alerts by marking them as acknowledged 
    # Or you can simply delete the logs if they are no longer needed
    # Here, we filter for Suicidal/Depression logs and update them
    logs_to_clear = EmotionLog.query.filter(
        (EmotionLog.emotion == "Suicidal") | (EmotionLog.emotion == "Depression")
    ).all()

    for log in logs_to_clear:
        # If you have an 'acknowledged' column, set it to True
        # If not, you can delete them:
        db.session.delete(log)
    
    db.session.commit()
    return redirect(url_for('counselor_dashboard'))
@app.route("/student/request_chat/<int:counselor_id>", methods=["POST"])
def student_request_chat(counselor_id):
    if "student_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    student_id = session["student_id"]

    # Check if a pending request already exists to avoid duplicates
    existing = ChatRequest.query.filter_by(
        student_id=student_id, 
        counselor_id=counselor_id, 
        status='pending'
    ).first()

    if not existing:
        new_request = ChatRequest(
            student_id=student_id,
            counselor_id=counselor_id,
            status='pending'
        )
        db.session.add(new_request)
        db.session.commit()
        return jsonify({"success": "Request sent to counselor!"})
    
    return jsonify({"info": "Request already pending."})

@app.route("/counselor/requests")
def counselor_view_requests():
    if "counselor_id" not in session:
        return redirect(url_for("counselor_login"))
        
    # Fetch requests specifically for this counselor that are still 'pending'
    incoming_requests = ChatRequest.query.filter_by(
        counselor_id=session['counselor_id'], 
        status='pending'
    ).all()
    
    return render_template("requests.html", requests=incoming_requests)

@app.route("/counselor/boost_student/<int:student_id>", methods=["POST"])
def boost_student(student_id):
    if "counselor_id" not in session:
        return redirect(url_for("counselor_login"))
    
    boosting_message = request.form.get("message")
    counselor_id = session["counselor_id"]

    # Create a new chat request with the boosting message
    new_request = ChatRequest(
        student_id=student_id,
        counselor_id=counselor_id,
        status='pending' # Student needs to accept
    )
    db.session.add(new_request)
    
    # Also log the boosting message into the AIChat table 
    # so the student sees it in their chat window immediately
    notification = AIChat(
        student_id=student_id,
        sender="counselor", # New sender type
        message=f"📢 MESSAGE FROM COUNSELOR: {boosting_message}"
    )
    db.session.add(notification)
    db.session.commit()

    
    return redirect(url_for("counselor_dashboard"))


@app.route("/student/accept_request/<int:request_id>")
def accept_counselor_request(request_id):
    req = ChatRequest.query.get_or_404(request_id)
    req.status = 'accepted'
    db.session.commit()
    return redirect(url_for('private_chat_room', request_id=req.id))

@app.route("/private_chat/<int:request_id>")
def private_chat_room(request_id):
    req = ChatRequest.query.get(request_id)
    # Note that we are passing 'chat_req=req' here
    return render_template("private_chat.html", chat_req=req)


# Route to see all students
@app.route("/counselor/view_students")
def view_students():
    all_students = Student.query.all()
    return render_template("view_students.html", students=all_students)

# Route to see chat requests
@app.route("/student/requests")
def student_view_requests():
    # Fetch requests where status is 'pending'
    requests = ChatRequest.query.filter_by(counselor_id=session['counselor_id'], status='pending').all()
    return render_template("requests.html", requests=requests)

# Route to accept a request

@app.route("/delete_event/<int:event_id>")
def delete_event(event_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    event = Notification.query.get(event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Create default accounts if they don't exist
        if not Admin.query.filter_by(email="nila@gmail.com").first():
            admin = Admin(
                name="nila Admin",
                email="nila@gmail.com",
                password=generate_password_hash("nila123")
            )
            db.session.add(admin)

        if not Counselor.query.filter_by(email="nadhi@gmail.com").first():
            counselor = Counselor(
                name="nadhi Counselor",
                email="nadhi@gmail.com",
                password=generate_password_hash("nadhi123"),
                education="M.A. Psychology",
                location="Chennai",
                profile_pic="nadhi.jpg"
            )
            db.session.add(counselor)

        db.session.commit()

    app.run(debug=True)
