# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request, send_file
import sqlite3, json, os, subprocess
from decimal import Decimal

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "flac_library.db")
ASTRA_PATH = os.environ.get("ASTRA_PATH", "")

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sql_commands')
def sql_commands():
    return render_template('sql_commands.html')

@app.route('/api/execute_sql', methods=['POST'])
def execute_sql():
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "Query cannot be empty"}), 400

        con = get_db()
        cur = con.cursor()
        
        # Execute query / script
        cur.execute(query)
        
        if cur.description:
            columns = [col[0] for col in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            con.close()
            return app.response_class(
                response=json.dumps({"columns": columns, "rows": rows, "rowcount": len(rows)}, cls=DecimalEncoder),
                mimetype='application/json'
            )
        else:
            con.commit()
            affected = cur.rowcount
            con.close()
            return jsonify({"message": f"Query executed successfully. Rows affected: {affected}", "rowcount": affected})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/stream/<int:song_id>')
def stream_song(song_id):
    try:
        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT file_path, title FROM Songs WHERE song_id = ?", (song_id,))
        row = cur.fetchone()
        con.close()
        if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(row["file_path"], mimetype="audio/flac", as_attachment=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/play/<int:song_id>', methods=['POST'])
def play_song(song_id):
    try:
        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT song_id, title, file_path, COALESCE(play_count, 0) AS play_count FROM Songs WHERE song_id = ?", (song_id,))
        row = cur.fetchone()
        if not row:
            con.close()
            return jsonify({"error": "Song not found"}), 404

        file_path = row["file_path"]
        title = row["title"]

        if not file_path or not os.path.exists(file_path):
            con.close()
            return jsonify({"error": f"Audio file not found on disk: {file_path}"}), 404

        # Update play count and commit
        cur.execute("UPDATE Songs SET play_count = play_count + 1 WHERE song_id = ?", (song_id,))
        con.commit()
        new_count = row["play_count"] + 1
        con.close()

        # Check launch parameter: 'local_app' (Astra.exe) or 'stream'
        use_astra = request.args.get('astra', 'false').lower() == 'true'
        if use_astra:
            if os.path.exists(ASTRA_PATH):
                subprocess.Popen([ASTRA_PATH, file_path])
            else:
                os.startfile(file_path)

        return jsonify({
            "success": True,
            "message": f"Playing '{title}'",
            "song_id": song_id,
            "stream_url": f"/stream/{song_id}",
            "play_count": new_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/songs')
def get_songs():
    try:
        con = get_db()
        cur = con.cursor()
        cur.execute("""
            SELECT
                s.song_id,
                s.title,
                a.name          AS artist,
                al.title        AS album,
                al.release_year,
                COALESCE(g.name, '')  AS genre,
                s.track_number,
                s.duration,
                s.file_size,
                aq.file_format,
                aq.bit_depth,
                aq.sample_rate,
                aq.bitrate,
                COALESCE(s.play_count, 0) AS play_count,
                COALESCE(s.rating, 0)     AS rating
            FROM Songs s
            JOIN Albums al      ON s.album_id   = al.album_id
            JOIN Artists a      ON al.artist_id = a.artist_id
            LEFT JOIN Genres g  ON s.genre_id   = g.genre_id
            LEFT JOIN AudioQuality aq ON s.quality_id = aq.quality_id
            ORDER BY a.name, al.release_year, s.track_number
        """)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return app.response_class(
            response=json.dumps(rows, cls=DecimalEncoder),
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        con = get_db()
        cur = con.cursor()
        cur.execute("""
            SELECT
                COUNT(*)                                    AS total_songs,
                COUNT(DISTINCT s.album_id)                  AS total_albums,
                COUNT(DISTINCT al.artist_id)                AS total_artists,
                ROUND(SUM(s.file_size) / (1024.0*1024*1024), 2) AS total_gb,
                ROUND(SUM(s.duration) / 3600.0, 1)         AS total_hours
            FROM Songs s
            JOIN Albums al ON s.album_id = al.album_id
        """)
        stats = dict(cur.fetchone())

        cur.execute("""
            SELECT aq.bit_depth, aq.sample_rate, COUNT(*) AS cnt
            FROM Songs s JOIN AudioQuality aq ON s.quality_id = aq.quality_id
            GROUP BY aq.bit_depth, aq.sample_rate
            ORDER BY aq.bit_depth DESC, aq.sample_rate DESC
        """)
        quality = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT g.name, COUNT(*) AS cnt
            FROM Songs s JOIN Genres g ON s.genre_id = g.genre_id
            GROUP BY g.name
            ORDER BY cnt DESC
            LIMIT 8
        """)
        genres = [dict(r) for r in cur.fetchall()]
        con.close()

        result = {
            "total_songs":      int(stats["total_songs"] or 0),
            "total_albums":     int(stats["total_albums"] or 0),
            "total_artists":    int(stats["total_artists"] or 0),
            "total_gb":         float(stats["total_gb"] or 0),
            "total_hours":      float(stats["total_hours"] or 0),
            "quality_breakdown": quality,
            "top_genres":        genres
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("ERROR: flac_library.db not found. Run scan_library.py first!")
    app.run(debug=True, port=5000)
