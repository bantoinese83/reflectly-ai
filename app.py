import csv
import datetime
import io
import logging
import os
from collections import defaultdict

import google.generativeai as genai
import pymupdf4llm
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, send_file, render_template
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from google.generativeai import GenerationConfig
from rake_nltk import Rake
from textblob import TextBlob
from werkzeug.exceptions import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app and database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///journal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)
db = SQLAlchemy(app)

# Configure the Google Generative AI SDK
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model
generation_config = GenerationConfig(
    temperature=1,
    top_p=0.95,
    top_k=64,
    max_output_tokens=8192,
    response_mime_type="text/plain",
)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)


# Define the User and JournalEntry models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=True)
    interests = db.Column(db.String(200), nullable=True)
    goals = db.Column(db.String(200), nullable=True)
    entries = db.relationship('JournalEntry', backref='user', lazy=True)


class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.UTC))
    entry = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    return 'positive' if polarity > 0 else 'negative' if polarity < 0 else 'neutral'


def extract_keywords(text):
    rake = Rake()
    rake.extract_keywords_from_text(text)
    return rake.get_ranked_phrases()


def generate_reflection(entry, user_id):
    # Get the user's past entries from the database
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return "User not found."
    past_entries = user.entries

    # Extract keywords from past entries
    keywords = set()
    for past_entry in past_entries:
        keywords.update(extract_keywords(past_entry.entry))

    # Analyze the sentiment of past entries
    past_sentiments = [analyze_sentiment(past_entry.entry) for past_entry in past_entries]
    positive_count = past_sentiments.count('positive')
    negative_count = past_sentiments.count('negative')
    neutral_count = past_sentiments.count('neutral')

    # Construct a more informative prompt
    prompt = f"""
    Reflect on this journal entry: '{entry}'. 
    Consider the following:

    - **Past Entries:** The user has previously written about: {', '.join(list(keywords)[:5])}
    - **Sentiment Analysis:** The user has expressed positive emotions {positive_count} times, negative emotions {negative_count} times, and neutral emotions {neutral_count} times in their past entries.
    - **Context:** How does the context of this entry compare to the user's past entries? Are there any significant events or patterns that stand out?
    - **Patterns:** Are there any recurring themes or insights that emerge from comparing this entry to the user's past writing?

    Provide a thoughtful and insightful reflection, keeping it gentle and positive. 
    """

    response = model.generate_content(prompt)
    return response.text


def get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id)
        db.session.add(user)
        db.session.commit()
    return user


def save_journal_entry(user, entry_text, sentiment, category):
    new_journal_entry = JournalEntry(entry=entry_text, sentiment=sentiment, user=user, category=category)
    db.session.add(new_journal_entry)
    db.session.commit()


def generate_trend_chart(entries):
    trends = defaultdict(list)
    for entry in entries:
        date = entry.timestamp.date()
        trends[date].append(entry.sentiment)

    dates = sorted(trends.keys())
    positive_trend = [sum(1 for sentiment in trends[date] if sentiment == 'positive') for date in dates]
    negative_trend = [sum(1 for sentiment in trends[date] if sentiment == 'negative') for date in dates]
    neutral_trend = [sum(1 for sentiment in trends[date] if sentiment == 'neutral') for date in dates]

    return {
        "dates": dates,
        "positive_trend": positive_trend,
        "negative_trend": negative_trend,
        "neutral_trend": neutral_trend
    }


def generate_metrics(entries):
    total_entries = len(entries)
    positive_count = sum(1 for entry in entries if entry.sentiment == 'positive')
    negative_count = sum(1 for entry in entries if entry.sentiment == 'negative')
    neutral_count = sum(1 for entry in entries if entry.sentiment == 'neutral')

    # Handle empty list case
    if total_entries == 0:
        return {
            "total_entries": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "positive_percentage": 0,
            "negative_percentage": 0,
            "neutral_percentage": 0,
        }

    return {
        "total_entries": total_entries,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "positive_percentage": (positive_count / total_entries) * 100,
        "negative_percentage": (negative_count / total_entries) * 100,
        "neutral_percentage": (neutral_count / total_entries) * 100,
    }


def send_daily_reminder():
    with app.app_context():
        users = User.query.all()
        for user in users:
            msg = Message('Daily Journal Reminder', sender='noreply@example.com', recipients=[user.email])
            msg.body = 'This is a reminder to write your daily journal entry.'
            mail.send(msg)


scheduler = BackgroundScheduler()
scheduler.add_job(func=send_daily_reminder, trigger="interval", days=1)
scheduler.start()


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return jsonify(error=str(e)), e.code
    logging.error(f"Unhandled exception: {e}")
    return jsonify(error="An internal error occurred"), 500


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/journal/<user_id>', methods=['POST'])
def journal_entry(user_id):
    try:
        entry = request.json.get('entry')
        category = request.json.get('category')
        if not entry:
            return jsonify({"error": "No journal entry provided"}), 400

        sentiment = analyze_sentiment(entry)
        keywords = extract_keywords(entry)
        user = get_user(user_id)
        save_journal_entry(user, entry, sentiment, category)
        reflection = generate_reflection(entry, user_id)

        return jsonify({"reflection": reflection, "keywords": keywords})
    except Exception as e:
        logging.error(f"Error processing journal entry: {e}")
        return jsonify({"error": "An error occurred while processing the journal entry"}), 500


@app.route('/reflect/<user_id>', methods=['GET'])
def get_reflection(user_id):
    try:
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        entries = user.entries
        metrics = generate_metrics(entries)
        trend_chart = generate_trend_chart(entries)
        reflection_prompt = f"This user has written {metrics['total_entries']} entries. They have mentioned positive emotions {metrics['positive_count']} times, negative emotions {metrics['negative_count']} times, and neutral emotions {metrics['neutral_count']} times. What overall trends do you notice about their emotional state? Provide a reflective summary."
        response = model.generate_content(reflection_prompt)

        return jsonify({"reflection": response.text, "trend_chart": trend_chart, "metrics": metrics})
    except Exception as e:
        logging.error(f"Error generating reflection: {e}")
        return jsonify({"error": "An error occurred while generating the reflection"}), 500


@app.route('/search/<user_id>', methods=['GET'])
def search_entries(user_id):
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return jsonify({"error": "No keyword provided"}), 400

        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        entries = JournalEntry.query.filter(JournalEntry.user_id == user.id, JournalEntry.entry.contains(keyword)).all()
        return jsonify([entry.entry for entry in entries])
    except Exception as e:
        logging.error(f"Error searching entries: {e}")
        return jsonify({"error": "An error occurred while searching the entries"}), 500


@app.route('/export/<user_id>', methods=['GET'])
def export_entries(user_id):
    try:
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        entries = user.entries
        export_format = request.args.get('format', 'csv')

        if export_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Timestamp', 'Entry', 'Sentiment', 'Category'])
            for entry in entries:
                writer.writerow([entry.timestamp, entry.entry, entry.sentiment, entry.category])
            output.seek(0)
            return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True,
                             download_name='journal_entries.csv')

        elif export_format == 'pdf':
            md_text = pymupdf4llm.to_markdown("input.pdf")
            output_file = io.BytesIO()
            output_file.write(md_text.encode())
            output_file.seek(0)
            return send_file(output_file, mimetype='application/pdf', as_attachment=True,
                             download_name='journal_entries.pdf')

        else:
            return jsonify({"error": "Invalid export format"}), 400
    except Exception as e:
        logging.error(f"Error exporting entries: {e}")
        return jsonify({"error": "An error occurred while exporting the entries"}), 500


@app.route('/share/<entry_id>', methods=['POST'])
def share_entry(entry_id):
    try:
        entry = JournalEntry.query.get(entry_id)
        if not entry:
            return jsonify({"error": "Entry not found"}), 404

        email = request.json.get('email')
        if not email:
            return jsonify({"error": "No email provided"}), 400

        msg = Message('Shared Journal Entry', sender='noreply@example.com', recipients=[email])
        msg.body = f"Timestamp: {entry.timestamp}\nEntry: {entry.entry}\nSentiment: {entry.sentiment}\nCategory: {entry.category}"
        mail.send(msg)

        return jsonify({"message": "Entry shared successfully"})
    except Exception as e:
        logging.error(f"Error sharing entry: {e}")
        return jsonify({"error": "An error occurred while sharing the entry"}), 500


if __name__ == '__main__':
    with app.app_context():
        logging.info("Creating database tables...")
        db.create_all()
        logging.info("Database tables created.")
    app.run(debug=True, host='127.0.0.1', port=5000)