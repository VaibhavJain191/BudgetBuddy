from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from flask_pymongo import PyMongo
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import defaultdict
import datetime
import pandas as pd
import io
from weasyprint import HTML
from functools import wraps

                       



                       
# Flask app setup
app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://VaibhavJain:vaibhav1324@budgetbuddy.vpmyy.mongodb.net/finance_db?retryWrites=true&w=majority&appName=BudgetBuddy"
app.secret_key = 'MUST FILL ALL COLUMNS'
mongo = PyMongo(app)




def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Check if the user is not logged in
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/')
def welcome():
    if 'user_id' in session:  # If the user is logged in, redirect to index.html
        return redirect(url_for('index'))
    return render_template('welcome.html')  # Show the welcome page
  # Show the welcome page

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:  # If already logged in, redirect to index
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check for empty fields
        if not username or not password or not confirm_password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        # Check if the username already exists
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists!', 'error')
            return redirect(url_for('register'))

        # Hash the password and save the user
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({'username': username, 'password': hashed_password})
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:  # If the user is already logged in, redirect to index
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = mongo.db.users.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))

        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    flash('You have been logged out.', 'success')
    return redirect(url_for('welcome'))

@app.route('/dashboard')
@login_required
def index():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'error')
        return redirect(url_for('login'))

    user_transactions = mongo.db.transactions.find({'user_id': session['user_id']})
    return render_template('index.html', username=session['username'], transactions=user_transactions)



@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        description = request.form['description']
        amount = request.form['amount']
        date = request.form['date']
        category = request.form['category']
        other_category = request.form.get('other_category')  # Get the specific name if provided
        payment_method = request.form['payment_method']
        notes = request.form['notes']

        # If "Others" is selected, use the specific name
        if category == "Others" and other_category:
            category = other_category

        # Basic validation
        if not description or not amount or not date or not category or not payment_method:
            flash('All fields are required!', 'error')
            return redirect(url_for('add_transaction'))

        try:
            amount = float(amount)
        except ValueError:
            flash('Amount must be a number!', 'error')
            return redirect(url_for('add_transaction'))

        # Include the user_id in the transaction document
        transaction = {
            'user_id': session['user_id'],  # Link transaction to the logged-in user
            'description': description,
            'amount': amount,
            'date': date,
            'category': category,
            'payment_method': payment_method,
            'notes': notes
        }

        try:
            mongo.db.transactions.insert_one(transaction)
            flash('Transaction added successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')

        return redirect(url_for('view_transactions'))

    return render_template('add_transaction.html')

@app.route('/view_transactions', methods=['GET', 'POST'])
@login_required
def view_transactions():
    try:
        # Get filter parameters from the request
        category_filter = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        amount_filter = request.args.get('amount')
        search_query = request.args.get('search')

        # Build the query
        query = {'user_id': session['user_id']}  # Filter transactions by user_id
        if category_filter:
            query['category'] = category_filter
        if start_date and end_date:
            query['date'] = {'$gte': start_date, '$lte': end_date}
        if amount_filter:
            amount = float(amount_filter)
            query['amount'] = {'$gte': amount}  # Adjust this as needed for filtering
        if search_query:
            query['description'] = {'$regex': search_query, '$options': 'i'}  # Case-insensitive search

        transactions = mongo.db.transactions.find(query)
        return render_template('view_transactions.html', transactions=transactions)

    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('view_transactions.html', transactions=[])
    
@app.route('/summary')
@login_required
def summary():
    try:
        # Fetch transactions for the logged-in user
        transactions = list(mongo.db.transactions.find({'user_id': session['user_id']}))
        
        # Calculate total income, expenses, and balance
        total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_expenses = sum(t['amount'] for t in transactions if t['amount'] < 0)
        balance = total_income + total_expenses

        # Calculate average daily spending
        if transactions:
            transaction_dates = [datetime.datetime.strptime(t['date'], "%Y-%m-%d") for t in transactions]
            earliest_date = min(transaction_dates)
            latest_date = max(transaction_dates)
            days_active = (latest_date - earliest_date).days + 1  # Include the first day
            avg_daily_spending = abs(total_expenses) / days_active
        else:
            avg_daily_spending = 0

        # Calculate top spending category
        category_expenses = {}
        for t in transactions:
            if t['amount'] < 0:  # Only consider expenses
                category_expenses[t['category']] = category_expenses.get(t['category'], 0) + abs(t['amount'])

        if category_expenses:
            top_category = max(category_expenses, key=category_expenses.get)
            top_category_amount = category_expenses[top_category]
        else:
            top_category = "N/A"
            top_category_amount = 0

        # Prepare data for charts
        chart_data = [
            {'date': t['date'], 'income': t['amount'] if t['amount'] > 0 else 0, 'expense': abs(t['amount']) if t['amount'] < 0 else 0}
            for t in transactions
        ]

        pie_chart_data = [{'category': cat, 'amount': amt} for cat, amt in category_expenses.items()]

        return render_template(
            'summary.html',
            total_income=total_income,
            total_expenses=total_expenses,
            balance=balance,
            avg_daily_spending=avg_daily_spending,
            top_category=top_category,
            top_category_amount=top_category_amount,
            line_chart_data=chart_data,
            pie_chart_data=pie_chart_data
        )
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('summary.html', total_income=0, total_expenses=0, balance=0, avg_daily_spending=0, top_category="N/A", top_category_amount=0, line_chart_data=[], pie_chart_data=[])

@app.route('/budget', methods=['GET', 'POST'])
@login_required
def budget():
    if request.method == 'POST':
        category = request.form['category']
        budget = request.form['budget']
        period = request.form['period']

        if not category or not budget or not period:
            flash('All fields are required!', 'error')
            return redirect(url_for('budget'))

        try:
            budget = float(budget)
        except ValueError:
            flash('Budget must be a number!', 'error')
            return redirect(url_for('budget'))

        budget_entry = {
            'user_id': session['user_id'],  # Link budget to the logged-in user
            'category': category,
            'budget': budget,
            'period': period,
            'spent': 0  # Default spent amount
        }

        try:
            mongo.db.budgets.update_one(
                {'user_id': session['user_id'], 'category': category, 'period': period},
                {'$set': budget_entry},
                upsert=True
            )
            flash('Budget set successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')

        return redirect(url_for('budget'))

    try:
        budgets = list(mongo.db.budgets.find({'user_id': session['user_id']}))
        transactions = list(mongo.db.transactions.find({'user_id': session['user_id']}))

        for budget in budgets:
            # Calculate total spent for the category and period
            budget['spent'] = abs(sum(
                t['amount'] for t in transactions
                if t['category'] == budget['category'] and t['amount'] < 0
            ))

            # Calculate remaining budget
            budget['remaining'] = budget['budget'] - budget['spent']

        return render_template('budget.html', budgets=budgets)
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('budget.html', budgets=[])

@app.route('/predictions')
@login_required
def predictions():
    try:
        # Fetch transactions for the logged-in user
        transactions = list(mongo.db.transactions.find({'user_id': session['user_id']}))
        
        # Calculate monthly income and expenses
        monthly_data = defaultdict(lambda: {'income': 0, 'expenses': 0})
        
        for transaction in transactions:
            month = transaction['date'][:7]  # Get the year-month (YYYY-MM)
            if transaction['amount'] > 0:
                monthly_data[month]['income'] += transaction['amount']
            else:
                monthly_data[month]['expenses'] += abs(transaction['amount'])

        # Prepare data for predictions (simple average for next 3 months)
        prediction_data = []
        months = sorted(monthly_data.keys())
        for i in range(1, 4):  # Predict for the next 3 months
            if months:
                last_month = months[-1]
                next_month = (datetime.datetime.strptime(last_month, "%Y-%m") + datetime.timedelta(days=31)).strftime("%Y-%m")
                avg_income = sum(monthly_data[m]['income'] for m in months[-3:]) / 3
                avg_expenses = sum(monthly_data[m]['expenses'] for m in months[-3:]) / 3
                prediction_data.append({
                    'month': next_month,
                    'predicted_income': avg_income,
                    'predicted_expenses': avg_expenses
                })
                months.append(next_month)

        return render_template('predictions.html', prediction_data=prediction_data)
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('predictions.html', prediction_data=[])
   

@app.route('/export_transactions', methods=['POST'])
@login_required
def export_transactions():
    try:
        # Fetch transactions for the logged-in user
        transactions = list(mongo.db.transactions.find({'user_id': session['user_id']}))
        df = pd.DataFrame(transactions)
        
        # Create a BytesIO stream for the CSV
        output = io.BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)  # Move to the beginning of the stream
        
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='transactions.csv')
    except Exception as e:
        flash(f'An error occurred while exporting: {str(e)}', 'error')
        return redirect(url_for('view_transactions'))

@app.route('/export_pdf', methods=['POST'])
@login_required
def export_pdf():
    try:
        # Fetch transactions for the logged-in user
        transactions = list(mongo.db.transactions.find({'user_id': session['user_id']}))
        df = pd.DataFrame(transactions)
        html = df.to_html()
        
        # Create a BytesIO stream for the PDF
        output = io.BytesIO()
        HTML(string=html).write_pdf(output)
        output.seek(0)  # Move to the beginning of the stream
        
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='transactions.pdf')
    except Exception as e:
        flash(f'An error occurred while exporting: {str(e)}', 'error')
        return redirect(url_for('view_transactions'))

@app.route('/import_transactions', methods=['POST'])
@login_required
def import_transactions():
    try:
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file.save(filename)  # Save the file temporarily
            
            if filename.endswith('.csv'):
                df = pd.read_csv(filename)
            elif filename.endswith('.xlsx'):
                df = pd.read_excel(filename)
            else:
                flash('Unsupported file format!', 'error')
                return redirect(url_for('view_transactions'))

            # Convert DataFrame to dictionary and insert into MongoDB
            transactions = df.to_dict(orient='records')
            for transaction in transactions:
                transaction['user_id'] = session['user_id']  # Link transaction to the logged-in user
            mongo.db.transactions.insert_many(transactions)
            flash('Transactions imported successfully!', 'success')
        else:
            flash('No file selected!', 'error')
    except Exception as e:
        flash(f'An error occurred while importing: {str(e)}', 'error')
    return redirect(url_for('view_transactions'))

@app.errorhandler(HTTPException)
def handle_exception(e):
    flash(f'An error occurred: {str(e)}', 'error')
    return render_template('error.html', error=str(e)), e.code

if __name__ == '__main__':
    app.run(debug=True)
