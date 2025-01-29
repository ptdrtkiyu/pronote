from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = "ma_cle_secrete" 

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
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_utilisateur VARCHAR(100) NOT NULL,
                mot_de_passe VARCHAR(100) NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_utilisateur VARCHAR(100) NOT NULL,
                mot_de_passe VARCHAR(100) NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                utilisateur_id INT,
                note FLOAT NOT NULL,
                matiere ENUM('Français', 'Maths', 'Histoire', 'Géographie') NOT NULL,  -- Ajout de la colonne matiere

                date_note TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id)
            )
        ''')
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
                        SELECT u.nom_utilisateur, n.note, n.matiere, n.date_note 
                        FROM notes n
                        JOIN utilisateurs u ON n.utilisateur_id = u.id
                    ''')

                    for row in cursor.fetchall():
                        nom = row['nom_utilisateur']
                        note = row['note']
                        matiere = row['matiere']
                        date_note = row['date_note']
                        
                        if nom not in notes_par_eleve:
                            notes_par_eleve[nom] = {}

                        if matiere not in notes_par_eleve[nom]:
                            notes_par_eleve[nom][matiere] = []

                        notes_par_eleve[nom][matiere].append({'note': note, 'date_note': date_note})

                elif role == 'eleve':
                    cursor.execute('''
                        SELECT n.matiere, n.note, n.date_note
                        FROM notes n
                        JOIN utilisateurs u ON n.utilisateur_id = u.id
                        WHERE u.nom_utilisateur = %s
                    ''', (utilisateur,))

                    notes_par_eleve[utilisateur] = {}

                    for row in cursor.fetchall():
                        matiere = row['matiere']
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
    if request.method == 'POST':
        role = request.form.get('role')
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']

        if not nom_utilisateur or not mot_de_passe:
            flash("Le nom d'utilisateur et le mot de passe sont requis.", "danger")
            return redirect(url_for('ajouter_utilisateur'))

        table = "utilisateurs" if role == "eleve" else "profs"

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                query = f"SELECT * FROM {table} WHERE nom_utilisateur = %s"
                cursor.execute(query, (nom_utilisateur,))
                utilisateur_existant = cursor.fetchone()

                if utilisateur_existant:
                    flash("Cet utilisateur existe déjà.", "danger")
                    return redirect(url_for('ajouter_utilisateur'))

                query_insert = f"INSERT INTO {table} (nom_utilisateur, mot_de_passe) VALUES (%s, %s)"
                cursor.execute(query_insert, (nom_utilisateur, mot_de_passe))
                conn.commit()
                flash("Compte créé avec succès!", "success")
                return redirect(url_for('index'))
            except Error as e:
                flash(f"Erreur lors de la création de l'utilisateur : {e}", "danger")
                conn.rollback()
            finally:
                conn.close()
        else:
            flash("Erreur de connexion à la base de données", "danger")

    return render_template('ajouter_utilisateur.html')



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
                
                cursor.execute("SELECT * FROM utilisateurs WHERE nom_utilisateur = %s AND mot_de_passe = %s", 
                               (nom_utilisateur, mot_de_passe))
                utilisateur = cursor.fetchone()

                if utilisateur:
                    session['utilisateur'] = utilisateur['nom_utilisateur']
                    session['role'] = 'eleve'
                    return redirect(url_for('index'))

                cursor.execute("SELECT * FROM profs WHERE nom_utilisateur = %s AND mot_de_passe = %s", 
                               (nom_utilisateur, mot_de_passe))
                prof = cursor.fetchone()

                if prof:
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
    session.pop('utilisateur', None)
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

@app.route('/ajouter_note', methods=['GET', 'POST'])
def ajouter_note():
    if 'utilisateur' in session and session.get('role') == 'prof':
        conn = get_db_connection()
        
        if request.method == 'POST':
            note = request.form['note']
            eleve_id = request.form['eleve_id']
            matiere = request.form['matiere']

            if not note or not eleve_id or not matiere:
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

            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM utilisateurs WHERE id = %s", (eleve_id,))
                eleve = cursor.fetchone()
                
                if eleve:
                    cursor.execute(
                        "INSERT INTO notes (utilisateur_id, note, matiere) VALUES (%s, %s, %s)", 
                        (eleve_id, note, matiere)
                    )
                    conn.commit()
                    flash("Note ajoutée avec succès pour l'élève.", "success")
                else:
                    flash("Élève introuvable.", "danger")
            except Error as e:
                flash(f"Erreur lors de l'ajout de la note : {e}", "danger")
                conn.rollback()
            finally:
                conn.close()

            return redirect(url_for('index'))
        else:
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom_utilisateur FROM utilisateurs")
                eleves = cursor.fetchall()
                conn.close()
                return render_template('ajouter_note.html', eleves=eleves)
    else:
        flash("Vous devez être connecté en tant que professeur pour ajouter une note.", "danger")
        return redirect(url_for('connexion'))



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
