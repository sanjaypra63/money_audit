from flask import Flask, request, render_template, redirect, url_for, flash, session, Response
import os
import re
import csv
import io
from PyPDF2 import PdfReader

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
    # Regex for Debit and Credit lines, handling commas in amounts
    debit_pattern = r'Debit\s*([₹€£$¥][\d,]+\.?\d*)'
    credit_pattern = r'Credit\s*([₹€£$¥][\d,]+\.?\d*)'
    debits = re.findall(debit_pattern, text)
    credits = re.findall(credit_pattern, text)
    transactions = []
    currency = None
    for d in debits:
        curr = d[0]
        amt_str = d[1:].replace(',', '')  # Remove commas
        try:
            amt = float(amt_str) * -1  # Debit is expense, negative
            transactions.append(amt)
            if not currency:
                currency = curr
        except ValueError:
            continue
    for c in credits:
        curr = c[0]
        amt_str = c[1:].replace(',', '')  # Remove commas
        try:
            amt = float(amt_str)  # Credit is income, positive
            transactions.append(amt)
            if not currency:
                currency = curr
        except ValueError:
            continue
    return transactions, currency

def analyze_transactions(transactions):
    credits = [t for t in transactions if t > 0]
    debits = [t for t in transactions if t < 0]
    total_in = sum(credits)
    total_out = sum(debits) * -1  # Make positive
    large_expenses = [abs(d) for d in debits if abs(d) > 100]
    small_spends = [abs(d) for d in debits if abs(d) <= 100]
    large_expenses_count = len(large_expenses)
    large_expenses_sum = sum(large_expenses)
    small_spends_count = len(small_spends)
    small_spends_sum = sum(small_spends)
    return total_in, total_out, large_expenses_count, large_expenses_sum, small_spends_count, small_spends_sum

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
            total_in, total_out, large_expenses_count, large_expenses_sum, small_spends_count, small_spends_sum = analyze_transactions(transactions)
            insight = get_insight(total_out, large_expenses_count)

            # Store raw results in session for CSV download
            session['results'] = {
                'total_in': total_in,
                'total_out': total_out,
                'large_expenses_count': large_expenses_count,
                'large_expenses_sum': large_expenses_sum,
                'small_spends_count': small_spends_count,
                'small_spends_sum': small_spends_sum,
                'insight': insight,
                'currency': currency
            }

            # Format results for display
            result = {
                'total_in': format_currency(total_in, currency),
                'total_out': format_currency(total_out, currency),
                'large_expenses_count': large_expenses_count,
                'large_expenses_sum': format_currency(large_expenses_sum, currency),
                'small_spends_count': small_spends_count,
                'small_spends_sum': format_currency(small_spends_sum, currency),
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

@app.route('/download_csv')
def download_csv():
    if 'results' not in session:
        return redirect(url_for('index'))

    results = session['results']
    currency = results['currency']

    def generate():
        data = [
            ['Metric', 'Value'],
            ['Total Money In', format_currency(results['total_in'], currency)],
            ['Total Money Out', format_currency(results['total_out'], currency)],
            ['Large Expenses (count)', results['large_expenses_count']],
            ['Large Expenses (sum)', format_currency(results['large_expenses_sum'], currency)],
            ['Small Daily Spends (count)', results['small_spends_count']],
            ['Small Daily Spends (sum)', format_currency(results['small_spends_sum'], currency)],
            ['Insight', results['insight']]
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        for row in data:
            writer.writerow(row)
        output.seek(0)
        return output.getvalue()

    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=analysis_results.csv"})

if __name__ == '__main__':
    app.run(debug=True)
