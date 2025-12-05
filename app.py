from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///growtive.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    level_tag = db.Column(db.String(20))  # SD/SMP/SMA
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    coins = db.Column(db.Integer, default=0)
    is_premium = db.Column(db.Boolean, default=False)
    streak_days = db.Column(db.Integer, default=0)
    last_login_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level_tag = db.Column(db.String(20))  # SD/SMP/SMA
    grade = db.Column(db.String(10))      # 1-12
    subject = db.Column(db.String(50))
    topic = db.Column(db.String(100))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    video_url = db.Column(db.String(255))
    is_premium = db.Column(db.Boolean, default=False)


class UserBookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'))


class UserNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level_tag = db.Column(db.String(20))
    subject = db.Column(db.String(50))
    mode = db.Column(db.String(20))  # one_on_one / group
    status = db.Column(db.String(20), default='waiting')  # waiting / active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RoomMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    plan = db.Column(db.String(20))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def get_level_from_xp(xp: int) -> int:
    if xp < 0:
        return 1
    return max(1, xp // 100 + 1)


def award_login_bonus(user: User):
    today = date.today()
    if user.last_login_date is None or user.last_login_date != today:
        yesterday = date.fromordinal(today.toordinal() - 1)
        if user.last_login_date == yesterday:
            user.streak_days = (user.streak_days or 0) + 1
        else:
            user.streak_days = 1

        user.xp += 10
        user.coins += 5
        user.last_login_date = today
        user.level = get_level_from_xp(user.xp)


def award_material_completion(user: User):
    user.xp += 30
    user.coins += 10
    user.level = get_level_from_xp(user.xp)


def award_study_session(user: User):
    user.xp += 50
    user.coins += 20
    user.level = get_level_from_xp(user.xp)


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return wrapper


@app.route('/')
def index():
    user = current_user()
    return render_template('landing.html', user=user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        level_tag = request.form['level_tag']

        if User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.')
            return redirect(url_for('register'))

        user = User(name=name, email=email, level_tag=level_tag)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registrasi berhasil, silakan login.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            award_login_bonus(user)
            db.session.commit()
            return redirect(url_for('dashboard'))
        flash('Email atau password salah.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Anda telah logout.')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    top_users = User.query.order_by(User.xp.desc()).limit(5).all()
    return render_template('dashboard.html', user=user, top_users=top_users)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        user.name = request.form['name']
        user.level_tag = request.form['level_tag']
        db.session.commit()
        flash('Profil diperbarui.')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)


@app.route('/library')
@login_required
def library():
    user = current_user()
    level_tag = request.args.get('level_tag') or user.level_tag
    grade = request.args.get('grade')
    subject = request.args.get('subject')

    query = Material.query
    if level_tag:
        query = query.filter_by(level_tag=level_tag)
    if grade:
        query = query.filter_by(grade=grade)
    if subject:
        query = query.filter_by(subject=subject)

    materials = query.all()
    return render_template(
        'library.html',
        user=user,
        materials=materials,
        level_tag=level_tag,
        grade=grade,
        subject=subject,
    )


@app.route('/material/<int:material_id>', methods=['GET', 'POST'])
@login_required
def material_detail(material_id):
    user = current_user()
    material = Material.query.get_or_404(material_id)

    if material.is_premium and not user.is_premium:
        locked = True
        return render_template('material_detail.html', user=user, material=material, locked=locked)

    locked = False

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'complete':
            award_material_completion(user)
            db.session.commit()
            flash('Belajar selesai! XP dan koin bertambah.')
        elif action == 'bookmark':
            if not UserBookmark.query.filter_by(user_id=user.id, material_id=material.id).first():
                db.session.add(UserBookmark(user_id=user.id, material_id=material.id))
                db.session.commit()
                flash('Materi dibookmark.')
        elif action == 'note':
            content = request.form.get('note_content', '').strip()
            if content:
                db.session.add(UserNote(user_id=user.id, material_id=material.id, content=content))
                db.session.commit()
                flash('Catatan disimpan.')
        return redirect(url_for('material_detail', material_id=material.id))

    bookmarks = UserBookmark.query.filter_by(user_id=user.id, material_id=material.id).all()
    notes = UserNote.query.filter_by(user_id=user.id, material_id=material.id).order_by(
        UserNote.created_at.desc()
    ).all()
    return render_template(
        'material_detail.html',
        user=user,
        material=material,
        locked=locked,
        bookmarks=bookmarks,
        notes=notes,
    )


@app.route('/study-room', methods=['GET', 'POST'])
@login_required
def study_room_lobby():
    user = current_user()
    if request.method == 'POST':
        level_tag = request.form['level_tag']
        subject = request.form['subject']
        mode = request.form['mode']
        room = match_or_create_room(user, level_tag, subject, mode)
        return redirect(url_for('study_room', room_id=room.id))
    return render_template('study_room_lobby.html', user=user)


def match_or_create_room(user, level_tag, subject, mode):
    max_members = 2 if mode == 'one_on_one' else 5
    rooms = Room.query.filter_by(level_tag=level_tag, subject=subject, mode=mode, status='waiting').all()
    for room in rooms:
        count = RoomMember.query.filter_by(room_id=room.id).count()
        if count < max_members:
            db.session.add(RoomMember(room_id=room.id, user_id=user.id))
            if count + 1 >= max_members:
                room.status = 'active'
            db.session.commit()
            return room
    new_room = Room(level_tag=level_tag, subject=subject, mode=mode, status='waiting')
    db.session.add(new_room)
    db.session.flush()
    db.session.add(RoomMember(room_id=new_room.id, user_id=user.id))
    db.session.commit()
    return new_room


@app.route('/study-room/<int:room_id>')
@login_required
def study_room(room_id):
    user = current_user()
    room = Room.query.get_or_404(room_id)
    messages = Message.query.filter_by(room_id=room.id).order_by(Message.created_at.asc()).all()
    return render_template('study_room.html', user=user, room=room, messages=messages)


@app.route('/study-room/<int:room_id>/end', methods=['POST'])
@login_required
def end_study_session(room_id):
    user = current_user()
    room = Room.query.get_or_404(room_id)
    award_study_session(user)
    db.session.commit()
    flash('Sesi belajar selesai! XP dan koin bertambah.')
    return redirect(url_for('dashboard'))


@app.route('/leaderboard')
@login_required
def leaderboard():
    user = current_user()
    users = User.query.order_by(User.xp.desc()).limit(10).all()
    return render_template('leaderboard.html', user=user, users=users)


@app.route('/upgrade')
@login_required
def upgrade():
    user = current_user()
    plans = [
        {'code': 'basic', 'name': 'Basic', 'price': 29000},
        {'code': 'pro', 'name': 'Pro', 'price': 49000},
        {'code': 'elite', 'name': 'Elite', 'price': 79000},
    ]
    return render_template('upgrade.html', user=user, plans=plans)


@app.route('/upgrade/<plan_code>', methods=['POST'])
@login_required
def upgrade_plan(plan_code):
    user = current_user()
    prices = {'basic': 29000, 'pro': 49000, 'elite': 79000}
    if plan_code not in prices:
        flash('Paket tidak ditemukan.')
        return redirect(url_for('upgrade'))

    amount = prices[plan_code]
    tx = Transaction(user_id=user.id, plan=plan_code, amount=amount, status='paid')
    user.is_premium = True
    db.session.add(tx)
    db.session.commit()
    flash('Pembayaran demo berhasil. Akun Anda sekarang premium.')
    return redirect(url_for('dashboard'))


@socketio.on('join')
def on_join(data):
    room_id = data.get('room_id')
    user_id = session.get('user_id')
    if not user_id or not room_id:
        return
    room_name = f"room-{room_id}"
    join_room(room_name)


@socketio.on('send_message')
def on_send_message(data):
    room_id = data.get('room_id')
    text = data.get('message', '').strip()
    user_id = session.get('user_id')
    if not user_id or not room_id or not text:
        return
    user = User.query.get(user_id)
    msg = Message(room_id=room_id, user_id=user_id, content=text)
    db.session.add(msg)
    db.session.commit()
    room_name = f"room-{room_id}"
    emit(
        'new_message',
        {
            'user_name': user.name,
            'content': text,
            'timestamp': msg.created_at.strftime('%H:%M'),
        },
        room=room_name,
    )


def init_db():
    db.create_all()
    if Material.query.count() == 0:
        sample = Material(
            level_tag='SMP',
            grade='8',
            subject='Matematika',
            topic='Persamaan Linear',
            title='Persamaan Linear Dasar',
            description='Materi dasar persamaan linear satu variabel.',
            video_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
            is_premium=False,
        )
        db.session.add(sample)
        db.session.commit()


if __name__ == '__main__':
    if not os.path.exists('growtive.db'):
        with app.app_context():
            init_db()
    socketio.run(app, debug=True)
