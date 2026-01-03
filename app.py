from flask import Flask, request, render_template, redirect, url_for, flash
import os
import re
from PyPDF2 import PdfReader
import tempfile

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For flash messages

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def parse_transactions(text):
    # Simple regex to find amounts with currency symbols
    # Assumes format like "Description ... ₹100.00" or "-₹50.00"
    amount_pattern = r'([₹€£$]?)(-?\d+\.?\d*)'
    matches = re.findall(amount_pattern, text)
    transactions = []
    currency = None
    for match in matches:
        symbol, amount = match
        if symbol:
            currency = symbol
        try:
            amt = float(amount)
            transactions.append(amt)
        except ValueError:
            continue
    return transactions, currency

def analyze_transactions(transactions):
    credits = [t for t in transactions if t > 0]
    debits = [t for t in transactions if t < 0]
    total_in = sum(credits)
    total_out = sum(debits) * -1  # Make positive
    large_expenses = [d for d in debits if abs(d) > 500]
    small_spends = [d for d in debits if abs(d) <= 500]
    return total_in, total_out, len(large_expenses), len(small_spends)

def get_insight(total_out, large_expenses_count):
    if total_out == 0:
        return "No money out detected"
    elif large_expenses_count > 0:
        return "Most money loss comes from a few large transactions"
    else:
        return "Spending is mostly small daily expenses"

def format_currency(amount, currency):
    if currency == '₹':
        return f"₹{amount:.2f}"
    elif currency == '€':
        return f"€{amount:.2f}"
    elif currency == '£':
        return f"£{amount:.2f}"
    elif currency == '$':
        return f"${amount:.2f}"
    else:
        return f"{amount:.2f}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and file.filename.endswith('.pdf'):
        # Save file temporarily
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Extract text
            text = extract_text_from_pdf(filepath)

            # Parse transactions
            transactions, currency = parse_transactions(text)

            if currency == '$':
                # For simplicity, assume USD, but in real app, ask user
                flash('Detected $ symbol. Assuming USD. For other currencies, please specify.')
                currency = '$'

            # Analyze
            total_in, total_out, large_count, small_count = analyze_transactions(transactions)
            insight = get_insight(total_out, large_count)

            # Format results
            result = {
                'total_in': format_currency(total_in, currency),
                'total_out': format_currency(total_out, currency),
                'large_expenses': large_count,
                'small_spends': small_count,
                'insight': insight
            }

            # Delete file
            os.remove(filepath)

            return render_template('index.html', result=result)

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            os.remove(filepath)
            return redirect(url_for('index'))
    else:
        flash('Only PDF files are allowed')
        return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True)
