from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
import bcrypt  

app = Flask(__name__)
app.secret_key = "ma_cle_secrete"

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password

def check_password(hashed_password, user_password):
    return bcrypt.checkpw(user_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="pronote"
        )
        return conn
    except Error as e:
        print(f"Erreur de connexion à la base de données : {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matieres (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_matiere VARCHAR(100) NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_utilisateur VARCHAR(100) UNIQUE NOT NULL,
                mot_de_passe VARCHAR(255) NOT NULL,
                role ENUM('eleve', 'prof', 'admin') DEFAULT 'eleve'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_utilisateur VARCHAR(100) NOT NULL,
                mot_de_passe VARCHAR(255) NOT NULL,
                matiere_id INT,
                FOREIGN KEY (matiere_id) REFERENCES matieres(id) ON DELETE SET NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                utilisateur_id INT,
                note FLOAT NOT NULL,
                matiere_id INT,
                date_note TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id) ON DELETE CASCADE,
                FOREIGN KEY (matiere_id) REFERENCES matieres(id) ON DELETE SET NULL
            )
        ''')


        cursor.execute("SELECT * FROM utilisateurs WHERE role = 'admin'")
        admin_existant = cursor.fetchone()

        if not admin_existant:
            hashed_password = hash_password("admin123").decode('utf-8')  
            cursor.execute("INSERT INTO utilisateurs (nom_utilisateur, mot_de_passe, role) VALUES (%s, %s, %s)", 
               ('admin', hashed_password, 'admin'))

            conn.commit()

        conn.close()

@app.route('/')
def index():
    role = session.get('role')
    utilisateur = session.get('utilisateur')
    notes_par_eleve = {}

    if utilisateur:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)

                if role == 'prof':
                    cursor.execute('''
                        SELECT u.nom_utilisateur, n.note, m.nom_matiere, n.date_note 
                        FROM notes n
                        JOIN utilisateurs u ON n.utilisateur_id = u.id
                        JOIN matieres m ON n.matiere_id = m.id
                    ''')
                    for row in cursor.fetchall():
                        nom = row['nom_utilisateur']
                        note = row['note']
                        matiere = row['nom_matiere']
                        date_note = row['date_note']

                        if nom not in notes_par_eleve:
                            notes_par_eleve[nom] = {}

                        if matiere not in notes_par_eleve[nom]:
                            notes_par_eleve[nom][matiere] = []

                        notes_par_eleve[nom][matiere].append({'note': note, 'date_note': date_note})

                elif role == 'eleve':
                    cursor.execute('''
                        SELECT m.nom_matiere, n.note, n.date_note
                        FROM notes n
                        JOIN utilisateurs u ON n.utilisateur_id = u.id
                        JOIN matieres m ON n.matiere_id = m.id
                        WHERE u.nom_utilisateur = %s
                    ''', (utilisateur,))

                    notes_par_eleve[utilisateur] = {}

                    for row in cursor.fetchall():
                        matiere = row['nom_matiere']
                        note = row['note']
                        date_note = row['date_note']

                        if matiere not in notes_par_eleve[utilisateur]:
                            notes_par_eleve[utilisateur][matiere] = []

                        notes_par_eleve[utilisateur][matiere].append({'note': note, 'date_note': date_note})

            except Error as e:
                flash(f"Erreur lors de la récupération des notes : {e}", "danger")
            finally:
                conn.close()

    return render_template('index.html', utilisateur=utilisateur, role=role, notes_par_eleve=notes_par_eleve)

@app.route('/ajouter_utilisateur', methods=['GET', 'POST'])
def ajouter_utilisateur():
    if 'utilisateur' not in session or session.get('role') != 'admin':
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        role = request.form.get('role')
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']
        matiere_id = request.form.get('matiere_id') if role == 'prof' else None

        if not nom_utilisateur or not mot_de_passe:
            flash("Les champs sont obligatoires.", "danger")
            return redirect(url_for('ajouter_utilisateur'))

        hashed_password = hash_password(mot_de_passe)

        conn = get_db_connection()
        cursor = conn.cursor()
        table = "utilisateurs" if role == "eleve" else "profs"

        try:
            cursor.execute(f"SELECT * FROM {table} WHERE nom_utilisateur = %s", (nom_utilisateur,))
            if cursor.fetchone():
                flash("Cet utilisateur existe déjà.", "danger")
                return redirect(url_for('ajouter_utilisateur'))

            if role == "prof" and matiere_id:
                cursor.execute(
                    "INSERT INTO profs (nom_utilisateur, mot_de_passe, matiere_id) VALUES (%s, %s, %s)",
                    (nom_utilisateur, hashed_password, matiere_id)
                )
            else:
                cursor.execute(
                    f"INSERT INTO {table} (nom_utilisateur, mot_de_passe) VALUES (%s, %s)",
                    (nom_utilisateur, hashed_password)
                )

            conn.commit()
            flash("Compte créé avec succès!", "success")
            return redirect(url_for('index'))
        except Error as e:
            flash(f"Erreur : {e}", "danger")
            conn.rollback()
        finally:
            conn.close()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM matieres")
    matieres = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('ajouter_utilisateur.html', matieres=matieres)

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']

        if not nom_utilisateur or not mot_de_passe:
            flash("Le nom d'utilisateur et le mot de passe sont requis.", "danger")
            return redirect(url_for('connexion'))

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)

                cursor.execute("SELECT * FROM utilisateurs WHERE nom_utilisateur = %s", (nom_utilisateur,))
                utilisateur = cursor.fetchone()

                if utilisateur and check_password(utilisateur['mot_de_passe'], mot_de_passe):
                    session['utilisateur'] = utilisateur['nom_utilisateur']
                    session['role'] = utilisateur['role']
                    return redirect(url_for('index'))

                cursor.execute("SELECT * FROM profs WHERE nom_utilisateur = %s", (nom_utilisateur,))
                prof = cursor.fetchone()

                if prof and check_password(prof['mot_de_passe'], mot_de_passe):
                    session['utilisateur'] = prof['nom_utilisateur']
                    session['role'] = 'prof'
                    return redirect(url_for('index'))

                flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
            except mysql.connector.Error as err:
                flash(f"Erreur de connexion : {err}", "danger")
            finally:
                conn.close()
        else:
            flash("Erreur de connexion à la base de données", "danger")

    return render_template('connexion.html')

@app.route('/deconnexion')
def deconnexion():
    if 'utilisateur' in session:
        session.pop('utilisateur', None)
        session.pop('role', None)
        flash("Vous avez été déconnecté avec succès.", "success")
    return redirect(url_for('index'))

@app.route('/supprimer', methods=['POST'])
def supprimer_compte():
    if 'utilisateur' in session:
        nom_utilisateur = session['utilisateur']
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM utilisateurs WHERE nom_utilisateur = %s", (nom_utilisateur,))
            conn.commit()
            conn.close()
            session.pop('utilisateur', None)
            flash(f"Le compte de {nom_utilisateur} a été supprimé avec succès.", "success")
            return redirect(url_for('index'))
        else:
            flash("Erreur de connexion à la base de données", "danger")
            return redirect(url_for('index'))
    else:
        flash("Vous devez être connecté pour supprimer votre compte.", "danger")
        return redirect(url_for('index'))

@app.route('/ajouter_note', methods=['GET', 'POST'])
def ajouter_note():
    if 'utilisateur' in session and session.get('role') == 'prof':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            note = request.form.get('note')
            utilisateur_id = request.form.get('utilisateur_id')
            matiere_id = request.form.get('matiere_id')

            if not note or not utilisateur_id or not matiere_id:
                flash("Tous les champs sont requis.", "danger")
                return redirect(url_for('ajouter_note'))

            try:
                note = float(note)
                if note < 0 or note > 20:
                    flash("La note doit être comprise entre 0 et 20.", "danger")
                    return redirect(url_for('ajouter_note'))
                note = round(note, 1)
            except ValueError:
                flash("Veuillez entrer une note valide.", "danger")
                return redirect(url_for('ajouter_note'))

            cursor.execute("SELECT id FROM utilisateurs WHERE id = %s AND role = 'eleve'", (utilisateur_id,))
            utilisateur = cursor.fetchone()

            if not utilisateur:
                flash("L'utilisateur sélectionné n'est pas un élève.", "danger")
                return redirect(url_for('ajouter_note'))

            cursor.execute("SELECT matiere_id FROM profs WHERE nom_utilisateur = %s", (session['utilisateur'],))
            prof_matiere = cursor.fetchone()

            if not prof_matiere:
                flash("Erreur : Le professeur n'a pas de matière associée.", "danger")
                return redirect(url_for('ajouter_note'))

            if int(matiere_id) != prof_matiere['matiere_id']:
                flash("Vous ne pouvez pas ajouter une note pour une matière qui ne vous est pas attribuée.", "danger")
                return redirect(url_for('ajouter_note'))

            cursor.execute("SELECT id FROM matieres WHERE id = %s", (matiere_id,))
            matiere = cursor.fetchone()

            if not matiere:
                flash("La matière sélectionnée n'existe pas.", "danger")
                return redirect(url_for('ajouter_note'))

            try:
                cursor.execute(
                    "INSERT INTO notes (utilisateur_id, note, matiere_id) VALUES (%s, %s, %s)",
                    (utilisateur_id, note, matiere_id)
                )
                conn.commit()
                flash("Note ajoutée avec succès.", "success")
            except Error as e:
                flash(f"Erreur lors de l'ajout de la note : {e}", "danger")
                conn.rollback()
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('index'))
        else:
            cursor.execute("SELECT matiere_id FROM profs WHERE nom_utilisateur = %s", (session['utilisateur'],))
            prof_matiere = cursor.fetchone()

            if prof_matiere:
                matiere_id = prof_matiere['matiere_id']
                cursor.execute("SELECT * FROM matieres WHERE id = %s", (matiere_id,))
                matieres = cursor.fetchall()
            else:
                matieres = []

            cursor.execute("SELECT id, nom_utilisateur FROM utilisateurs WHERE role = 'eleve'")
            utilisateurs = cursor.fetchall()

            cursor.close()
            conn.close()

            return render_template('ajouter_note.html', utilisateurs=utilisateurs, matieres=matieres)
    else:
        flash("Vous devez être connecté en tant que professeur pour ajouter une note.", "danger")
        return redirect(url_for('connexion'))

@app.route('/ajouter_matiere', methods=['GET', 'POST'])
def ajouter_matiere():
    if 'utilisateur' not in session or session.get('role') != 'admin':
        flash("Vous devez être un administrateur pour ajouter une matière.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        nom_matiere = request.form['nom_matiere']

        if not nom_matiere:
            flash("Le nom de la matière est requis.", "danger")
            return redirect(url_for('ajouter_matiere'))

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM matieres WHERE nom_matiere = %s", (nom_matiere,))
                if cursor.fetchone():
                    flash("Cette matière existe déjà.", "danger")
                else:
                    cursor.execute("INSERT INTO matieres (nom_matiere) VALUES (%s)", (nom_matiere,))
                    conn.commit()
                    flash("Matière ajoutée avec succès.", "success")
                return redirect(url_for('index'))
            except Error as e:
                flash(f"Erreur lors de l'ajout de la matière : {e}", "danger")
                conn.rollback()
            finally:
                conn.close()
        else:
            flash("Erreur de connexion à la base de données", "danger")

    return render_template('ajouter_matiere.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)