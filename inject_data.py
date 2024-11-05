import datetime
import random
from app import app, db, User, JournalEntry, analyze_sentiment

# Sample data for journal entries, categorized for more context
entries = {
    "Work": [
        "Today was a great day! I accomplished a lot at work and felt very productive.",
        "Work was stressful today. Too many deadlines and not enough time.",
        "Excited about the new project I'm working on. It's challenging but rewarding.",
        "Had a productive meeting with the team. We made significant progress.",
        "Had a tough day at work. Need to find a way to manage stress better.",
        "Feeling proud of my achievements at work.",
        "Feeling a bit overwhelmed with responsibilities.",
        "Had a productive day working on my side project.",
        "Feeling a bit stressed about the workload.",
        "Had a productive day working on my goals.",
        "Feeling a bit anxious about the new project.",
        "Lost my job today. Feeling scared about the future."
    ],
    "Personal": [
        "Feeling a bit down today. Things didn't go as planned.",
        "Feeling neutral today. Nothing special happened.",
        "Had a relaxing day at home. Watched movies and read a book.",
        "Feeling anxious about the upcoming presentation.",
        "Went for a long walk today. It was refreshing and cleared my mind.",
        "Feeling tired today. Need to get more rest.",
        "Had a peaceful day. Spent time meditating and reflecting.",
        "Feeling excited about the weekend plans. Looking forward to it.",
        "Had a challenging day. Faced some obstacles but managed to overcome them.",
        "Went to the gym today. Feeling energized and healthy.",
        "Feeling a bit lonely today. Missing my friends.",
        "Feeling stressed about the upcoming exams.",
        "Feeling grateful for the small things in life.",
        "Feeling inspired after reading a motivational book.",
        "Feeling anxious about the future. Need to stay positive.",
        "Feeling a bit under the weather today. Need to rest.",
        "Feeling a bit down today. Need to focus on self-care.",
        "Feeling grateful for the beauty of nature."
    ],
    "Family": [
        "Had a wonderful time with family. We went to the park and had a picnic.",
        "Feeling grateful for my friends and family. They are always there for me.",
        "Feeling a bit homesick today. Missing my family.",
        "Feeling happy after spending time with loved ones."
    ],
    "Health": [
        "Went to the gym today. Feeling energized and healthy.",
        "Feeling a bit under the weather today. Need to rest.",
        "Received a medical diagnosis. Feeling worried and anxious."
    ],
    "Hobbies": [
        "Had a relaxing day at home. Watched movies and read a book.",
        "Went for a long walk today. It was refreshing and cleared my mind.",
        "Had a relaxing day at the spa. Feeling rejuvenated.",
        "Feeling motivated to start a new hobby.",
        "Had a relaxing day reading by the fireplace.",
        "Had a productive day learning new skills.",
        "Had a fun day baking cookies. They turned out great.",
        "Had a peaceful day practicing yoga. Feeling centered.",
        "Had a peaceful day gardening. Nature is so calming.",
        "Had a fun day at the amusement park. Lots of excitement.",
        "Had a productive day working on my side project.",
        "Had a great time at the art gallery. So inspiring.",
        "Had a fun day playing sports with friends.",
        "Had a relaxing day at the beach. The waves were soothing."
    ],
    "Social": [
        "Had a fun day out with friends. We went to a new restaurant.",
        "Had a fun game night with friends. Lots of laughter.",
        "Feeling happy after spending time with loved ones.",
        "Had a great time at the beach. The weather was perfect.",
        "Feeling a bit lonely today. Missing my friends.",
        "Had a fun day at the concert. The music was amazing.",
        "Had a great time at the festival. So much fun.",
        "Feeling happy after reconnecting with an old friend.",
        "Had a great time at the festival. So much fun."
    ]
}

categories = ["Work", "Personal", "Family", "Health", "Hobbies", "Social"]

# Function to generate a random date within the last two months
def random_date():
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=60)
    return start_date + (end_date - start_date) * random.random()

with app.app_context():
    # Ensure the user exists
    user_id = "test_user"
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            email="test_user@example.com",
            age=30,
            interests="Reading, Hiking, Coding",
            goals="Become a better developer, Stay healthy"
        )
        db.session.add(user)
        db.session.commit()

    # Inject journal entries with categories
    for _ in range(60):
        category = random.choice(categories)
        entry_text = random.choice(entries[category])
        sentiment = analyze_sentiment(entry_text)
        timestamp = random_date()

        new_journal_entry = JournalEntry(
            entry=entry_text,
            sentiment=sentiment,
            category=category,
            user_id=user.id,
            timestamp=timestamp
        )
        db.session.add(new_journal_entry)

    db.session.commit()
    print("Mock journal entries with categories have been added to the database.")