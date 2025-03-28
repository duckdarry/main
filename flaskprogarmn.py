import os
import csv
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = 'asasaddad'

# DB faila ceļš
DATABASE = os.path.join(app.root_path, 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """DB inits, ja DB nav formatēts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Izveido un pārbauda vai ir tabula ratings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId INTEGER,
            movieId INTEGER,
            rating REAL,
            timestamp INTEGER
        )
    ''')
    
    # Pārbauda vai ir tabula movies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            movieId INTEGER PRIMARY KEY,
            title TEXT,
            genres TEXT
        )
    ''')
    
    # Tabula, lai izsekotu augšupielādētajiem failiem
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upload_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_type TEXT,  -- New column to track file type
            upload_date TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


init_db()

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # pārbauda vai  faili jau ir un neveidojas konflikti (ar pieprasījumiem)
    cursor.execute("SELECT filename FROM upload_info WHERE file_type = 'ratings' ORDER BY id DESC LIMIT 1")
    ratings_uploaded = cursor.fetchone()
    ratings_filename = ratings_uploaded['filename'] if ratings_uploaded else None

    cursor.execute("SELECT filename FROM upload_info WHERE file_type = 'movies' ORDER BY id DESC LIMIT 1")
    movies_uploaded = cursor.fetchone()
    movies_filename = movies_uploaded['filename'] if movies_uploaded else None

    if request.method == 'POST':
        if 'csvFile' not in request.files:
            flash('No file part in the request', 'danger')
            return redirect(request.url)
        file = request.files['csvFile']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        if file:
            try:
                # pieprasījums, lai dzēstu no db
                cursor.execute("DELETE FROM ratings")
                conn.commit()

                # Nolasa CSV un sadala pa rindām, ievieto db ar pieprasījumu
                stream = file.stream.read().decode("UTF8")
                csv_reader = csv.DictReader(stream.splitlines())
                rows_inserted = 0
                for row in csv_reader:
                    cursor.execute('''
                        INSERT INTO ratings (userId, movieId, rating, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (row['userId'], row['movieId'], row['rating'], row['timestamp']))
                    rows_inserted += 1
                conn.commit()

                # atjaunina info par failu
                cursor.execute("DELETE FROM upload_info WHERE file_type = 'ratings'")
                cursor.execute('''
                    INSERT INTO upload_info (filename, file_type, upload_date)
                    VALUES (?, 'ratings', datetime('now'))
                ''', (file.filename,))
                conn.commit()
                
                flash(f'Successfully uploaded {rows_inserted} records from {file.filename}.', 'success')
                return redirect(url_for('upload_csv'))
            except Exception as e:
                conn.rollback()
                flash(f'Error processing file: {e}', 'danger')
                return redirect(request.url)
    conn.close()
    return render_template('upload.html', ratings_filename=ratings_filename, movies_filename=movies_filename)

@app.route('/upload_movies_csv', methods=['POST'])
def upload_movies_csv():
    # movies csv faila augšupielādes handlings
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if 'moviesCsvFile' not in request.files:
        flash('No file part in the request', 'danger')
        return redirect(request.url)
    file = request.files['moviesCsvFile']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(request.url)
    
    if file:
        try:
            # Pa rindām ievieto db ar pieprasījumu
            stream = file.stream.read().decode("UTF8")
            csv_reader = csv.DictReader(stream.splitlines())
            rows_inserted = 0
            for row in csv_reader:
                cursor.execute('''
                    INSERT INTO movies (movieId, title, genres)
                    VALUES (?, ?, ?)
                ''', (row['movieId'], row['title'], row['genres']))
                rows_inserted += 1
            conn.commit()

            # atjaunina info par augšupielādēto failu
            cursor.execute("DELETE FROM upload_info WHERE file_type = 'movies'")
            cursor.execute('''
                INSERT INTO upload_info (filename, file_type, upload_date)
                VALUES (?, 'movies', datetime('now'))
            ''', (file.filename,))
            conn.commit()
            
            flash(f'Successfully uploaded {rows_inserted} movie records from {file.filename}.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error processing file: {e}', 'danger')
        return redirect(url_for('upload_csv'))
    
    conn.close()
    return redirect(url_for('upload_csv'))

@app.route('/clear_upload', methods=['POST'])
def clear_upload():
    # Dzēš visu augšupielādēto failu info no db
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # dzēš tabulu datus
        cursor.execute("DELETE FROM ratings")
        cursor.execute("DELETE FROM movies")
        cursor.execute("DELETE FROM upload_info")
        conn.commit()
        flash("Database contents cleared successfully.", "success")
    except Exception as e:
        flash(f"Error clearing database: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('upload_csv'))

@app.route('/visualizations')
def visualizations():
    # Ceļš un metodes vizualizācijas datiem
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pieprasījums vērtējumu sadalījumam
    cursor.execute('''
        SELECT rating, COUNT(*) AS count 
        FROM ratings 
        GROUP BY rating 
        ORDER BY rating
    ''')
    rating_data = cursor.fetchall()
    rating_labels = [str(row['rating']) for row in rating_data]
    rating_counts = [row['count'] for row in rating_data]
    
    # Pieprasījums vidējam vērtējumam pa mēnešiem
    cursor.execute('''
        SELECT strftime('%Y-%m', datetime(timestamp, 'unixepoch')) AS month, AVG(rating) AS avg_rating
        FROM ratings 
        GROUP BY month 
        ORDER BY month
    ''')
    time_data = cursor.fetchall()
    time_labels = [row['month'] for row in time_data]
    avg_ratings = [round(row['avg_rating'], 2) for row in time_data]

    conn.close()
    
    # Bez datiem nenotiek
    no_data = False
    if not rating_labels or not time_labels:
        no_data = True
        rating_labels = ["1", "2", "3", "4", "5"]
        rating_counts = [0, 0, 0, 0, 0]
        time_labels = []
        avg_ratings = []
    
    return render_template(
        'visualizations.html',
        rating_labels=rating_labels,
        rating_counts=rating_counts,
        time_labels=time_labels,
        avg_ratings=avg_ratings,
        no_data=no_data
    )


@app.route('/get_chart_data')
def get_chart_data():
    """Fetch dynamic chart data from the database with optional period filtering."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get optional start_date and end_date from query parameters
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)

        # Query 1: Rating Distribution
        cursor.execute('''
            SELECT rating, COUNT(*) AS count 
            FROM ratings 
            GROUP BY rating 
            ORDER BY rating
        ''')
        rating_data = cursor.fetchall()
        rating_labels = [str(row['rating']) for row in rating_data]
        rating_counts = [row['count'] for row in rating_data]

        # Query 2: Average Rating Over Time (grouped by month)
        if start_date and end_date:
            cursor.execute('''
                SELECT strftime('%Y-%m', datetime(timestamp, 'unixepoch')) AS month, AVG(rating) AS avg_rating
                FROM ratings 
                WHERE datetime(timestamp, 'unixepoch') BETWEEN ? AND ?
                GROUP BY month 
                ORDER BY month
            ''', (start_date, end_date))
        else:
            cursor.execute('''
                SELECT strftime('%Y-%m', datetime(timestamp, 'unixepoch')) AS month, AVG(rating) AS avg_rating
                FROM ratings 
                GROUP BY month 
                ORDER BY month
            ''')
        time_data = cursor.fetchall()
        time_labels = [row['month'] for row in time_data]
        avg_ratings = [round(row['avg_rating'], 2) for row in time_data]

        conn.close()

        # Return the data as JSON
        return jsonify({
            "rating_labels": rating_labels,
            "rating_counts": rating_counts,
            "time_labels": time_labels,
            "avg_ratings": avg_ratings
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_filtered_movies')
def get_filtered_movies():
    # Filtrs filmu sadalījumam pēc filmu vērtējuma
    try:
        # iegūst filmu datus
        min_rating = float(request.args.get('min_rating', 0))
        max_rating = float(request.args.get('max_rating', 5))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ar pieprasījumu iegūst no db
        cursor.execute('''
            SELECT m.title, AVG(r.rating) AS avg_rating
            FROM movies m
            JOIN ratings r ON m.movieId = r.movieId
            GROUP BY m.movieId
            HAVING avg_rating BETWEEN ? AND ?
            ORDER BY avg_rating DESC
        ''', (min_rating, max_rating))
        filtered_movies = cursor.fetchall()

        movie_titles = [row['title'] for row in filtered_movies]
        movie_ratings = [round(row['avg_rating'], 2) for row in filtered_movies]

        conn.close()

        return jsonify({'movie_titles': movie_titles, 'movie_ratings': movie_ratings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
if __name__ == '__main__':
    app.run(debug=True)
    
git commit -m "faili no visual studio code"
git push
