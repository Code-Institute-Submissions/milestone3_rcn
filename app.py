import os, datetime
from flask import Flask, render_template, redirect, request, url_for, flash, session
from forms import loginForm, registrationForm
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from bson.objectid import ObjectId
from os import path
if path.exists('env.py'):
    import env

app = Flask(__name__)

app.config['MONGO_DBNAME'] = os.environ.get('MONGO_DBNAME')
app.config['MONGO_URI'] = os.environ.get('MONGO_URI')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

mongo = PyMongo(app)
bcrypt = Bcrypt(app)


@app.route('/')
@app.route('/shared_login', methods=['GET', 'POST'])
def shared_login():
    form = loginForm()
    users = mongo.db.users
    if 'username' in session:
        user = users.find_one({'username': session['username']})
        return redirect(url_for(f'{user["role"]}_home', username=session['username']))
    if request.method == 'POST':
        user = users.find_one({'username': form.username.data})
        if user and bcrypt.check_password_hash(user['password'], form.password.data):
            session['username'] = form.username.data
            flash(f'Welcome {user["first_name"]}. You are logged in to your {user["role"]} account.', 'success')
            return redirect(url_for(f'{user["role"]}_home', username=session['username']))
        else:
            flash('Email/password combination is not recognised', 'danger')
            return render_template('shared_login.html', form=form, title='Login')
    return render_template('shared_login.html', form=form, title='Login')


@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if 'username' in session:
        return redirect(url_for(f'{role}_home', username=session['username']))
    form = registrationForm()
    if request.method == 'POST':
        users = mongo.db.users
        current_user = users.find_one({'username': request.form['email']})

        if current_user is None:
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            new_user = {
                'role': role,
                'first_name': form.first_name.data,
                'last_name': form.last_name.data,
                'username': form.email.data,
                'email': form.email.data,
                'telephone': form.telephone.data,
                'job_title': form.job_title.data,
                'password': hashed_password
            }
            users.insert_one(new_user)
            if role == 'member':
                users.update_one({'_id': new_user['_id']}, 
                                {"$set": {'employer': form.employer.data}})
            if role == 'staff':
                users.update_one({'_id': new_user['_id']}, 
                                {"$set": {'workplace': form.workplace.data}})
            session['username'] = form.email.data
            flash(f'{role} account created for {form.first_name.data}', 'success')
            return redirect(url_for(f'{role}_home', username=session['username']))
        else:
            flash(f'{form.email.data} is already registered. You can login by clicking the link below', 'danger')
    return render_template('register.html', form=form, title=f'{role} Sign Up', role=role)


@app.route('/member_home/<username>')
def member_home(username):
    user = mongo.db.users.find_one({'username': username})
    questions = mongo.db.questions.find({'member_id': username})
    assigned = mongo.db.questions.find({'staff_id': username})
    return render_template('member_home.html', 
                            member=user,
                            questions=questions, 
                            role=user['role'],
                            title=f"{user['first_name']}'s {user['role']} Home Page")


@app.route('/new_contact/<question_id>', methods=['GET', 'POST'])
def new_contact(question_id):
    contacts = mongo.db.contacts
    question = mongo.db.questions.find_one({'_id': ObjectId(question_id)})
    user = mongo.db.users.find_one({'username': session['username']})
    if request.method == 'POST':
        contact = {
            'member_id': session['username'],
            'question_id': ObjectId(question_id),
            'contact_type': 'database',
            'date': datetime.datetime.utcnow().strftime('%d/%m/%y  %H:%M'),
            'summary': request.form.get('summary'),
            'from': user['first_name'] + user['last_name'],
            'to': 'RCN'
        }
        contacts.insert_one(contact)
        flash("Thanks for getting in touch. Your RCN Lead will be in touch shortly. Check your contacts below for updates", 'success')
        return redirect(url_for('question_details', question_id=question['_id']))
    return render_template('new_contact.html', title='Contact your RCN Lead', question=question)


@app.route('/edit_contact/<contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact = mongo.db.contacts.find_one({'_id': ObjectId(contact_id)})
    question = mongo.db.questions.find_one({'_id': ObjectId(contact['question_id'])})
    if request.method == 'POST':
        mongo.db.contacts.update( 
            {'_id': ObjectId(contact_id)}, 
            { '$set': 
                {
                    'summary': request.form.get('summary')
                }
            })
        flash("Your contact has been updated.", 'success')
        return redirect(url_for('question_details', question_id=question['_id']))        
    return render_template('edit_contact.html', contact=contact, question=question, title='Edit Contact') 


@app.route('/account/<username>')
def account(username):
    user = mongo.db.users.find_one({'username': username})
    return render_template('account.html', 
                            member=user,
                            title=f"{user['first_name']}'s Account")


@app.route('/edit_account/<username>', methods=['GET', 'POST'])
def edit_account(username):
    mongo.db.users.update( 
        {'username': username}, 
        { '$set': 
            {
                'email': request.form.get('email'),
                'telephone': request.form.get('telephone'),
                'employer': request.form.get('employer'),
                'job_title': request.form.get('job_title')
            }
        })
    flash("Your details are now updated.", 'success')
    return redirect(url_for('account', username=session['username']))


@app.route('/new_question')
def new_question():
    return render_template('new_question.html', title='Ask a New Question')


@app.route('/submit_question', methods=['POST'])
def submit_question():
    questions = mongo.db.questions
    question = {
        'member_id': session['username'],
        'question_type': request.form.get('question_type'),
        'start_date': datetime.datetime.utcnow().strftime('%d/%m/%y  %H:%M'),
        'summary': request.form.get('summary'),
        'staff_id': 'unassigned'
    }
    questions.insert_one(question)
    flash("Thanks for your question. We'll respond shortly. You can click on your question below for updates.", 'success')
    return redirect(url_for('member_home', username=session['username']))


@app.route('/question_details/<question_id>')
def question_details(question_id):
    contacts = mongo.db.contacts.find({'question_id': ObjectId(question_id)})
    question = mongo.db.questions.find_one({'_id': ObjectId(question_id)})
    return render_template('question_details.html', contacts=contacts, question=question)


@app.route('/log_out')
def log_out():
    session.pop('username', None)
    flash('You are now logged out', 'success')
    return redirect(url_for('shared_login'))


#STAFF SIDE OF SITE


@app.route('/staff_home/<username>')
def staff_home(username):
    staff = mongo.db.staff.find_one({'username': session['username']})
    questions = mongo.db.questions.find({'staff_id': username})
    return render_template('staff_home.html', username=session['username'], staff=staff, questions=questions, title='Staff Home Page')


@app.route('/unassigned_questions')
def unassigned_questions():
    questions = mongo.db.questions
    unassigned = questions.find({'staff_id': 'unassigned'})
    return render_template('unassigned_questions.html', questions=unassigned, title='Unassigned Questions')


@app.route('/staff_question_details/<question_id>')
def staff_question_details(question_id):
    contacts = mongo.db.contacts.find({'question_id': ObjectId(question_id)})
    question = mongo.db.questions.find_one({'_id': ObjectId(question_id)})
    member = mongo.db.members.find_one({'username': question['member_id']})
    staff = mongo.db.staff
    return render_template('staff_question_details.html', contacts=contacts, question=question, member=member, staff=staff)


@app.route('/staf_new_contact/<question_id>', methods=['GET', 'POST'])
def staff_new_contact(question_id):
    contacts = mongo.db.contacts
    question = mongo.db.questions.find_one({'_id': ObjectId(question_id)})
    member = mongo.db.members.find_one({'username': question['member_id']})
    if request.method == 'POST':
        contact = {
            'member_id': question['member_id'],
            'question_id': ObjectId(question_id),
            'contact_type': request.form.get('contact_type'),
            'date': request.form.get('date'),
            'summary': request.form.get('summary'),
            'from': request.form.get('from'),
            'to': request.form.get('to'),
            'recorded_by': session['username'],
            'recorded_on': datetime.datetime.utcnow().strftime('%d/%m/%y  %H:%M')
        }
        contacts.insert_one(contact)
        flash("Your contact has been added. The member can now view your contacts", 'success')
        return redirect(url_for('staff_question_details', question_id=question['_id']))
    return render_template('staff_new_contact.html', title='Add a Contact', question=question)

# SHARED SITE


if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=int(os.environ.get('PORT')),
            debug=True)
