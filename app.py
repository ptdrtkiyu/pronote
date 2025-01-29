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
                note TEXT NOT NULL,
                FOREIGN KEY (utilisateur_id) REFERENCES utilisateurs(id)
            )
        ''')
        conn.commit()
        conn.close()

@app.route('/')
def index():
    utilisateur = session.get('utilisateur')
    notes = []
    if utilisateur:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id FROM utilisateurs WHERE nom_utilisateur = %s", (utilisateur,))
                utilisateur_data = cursor.fetchone()
                if utilisateur_data:
                    utilisateur_id = utilisateur_data['id']
                    cursor.execute("SELECT * FROM notes WHERE utilisateur_id = %s", (utilisateur_id,))
                    notes = cursor.fetchall()
            finally:
                conn.close()
    return render_template('index.html', utilisateur=utilisateur, notes=notes)

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
        role = request.form.get('role')
        nom_utilisateur = request.form['nom_utilisateur']
        mot_de_passe = request.form['mot_de_passe']

        if not nom_utilisateur or not mot_de_passe:
            flash("Le nom d'utilisateur et le mot de passe sont requis.", "danger")
            return redirect(url_for('connexion'))

        table = "utilisateurs" if role == "eleve" else "profs"

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                query = f"SELECT * FROM {table} WHERE nom_utilisateur = %s AND mot_de_passe = %s"
                cursor.execute(query, (nom_utilisateur, mot_de_passe))
                utilisateur = cursor.fetchone()

                if utilisateur:
                    session['utilisateur'] = utilisateur['nom_utilisateur']
                    session['role'] = role
                    flash("Connexion réussie!", "success")
                    return redirect(url_for('index'))
                else:
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
    flash("Déconnexion réussie.", "success")
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
    if 'utilisateur' in session:
        if request.method == 'POST':
            note = request.form['note']

            # Validation pour s'assurer que la note est un nombre valide
            try:
                note_valeur = float(note)
                if not (0 <= note_valeur <= 20):
                    flash("La note doit être comprise entre 0 et 20.", "danger")
                    return redirect(url_for('ajouter_note'))
            except ValueError:
                flash("Veuillez entrer une note valide.", "danger")
                return redirect(url_for('ajouter_note'))

            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT id FROM utilisateurs WHERE nom_utilisateur = %s", (session['utilisateur'],))
                    utilisateur = cursor.fetchone()

                    if utilisateur:
                        utilisateur_id = utilisateur['id']
                        cursor.execute("INSERT INTO notes (utilisateur_id, note) VALUES (%s, %s)", 
                                       (utilisateur_id, note_valeur))
                        conn.commit()
                        flash("Note ajoutée avec succès!", "success")
                        return redirect(url_for('index'))
                except Error as e:
                    flash(f"Erreur lors de l'ajout de la note : {e}", "danger")
                    conn.rollback()
                finally:
                    conn.close()
            else:
                flash("Erreur de connexion à la base de données", "danger")
                return redirect(url_for('index'))
        return render_template('ajouter_note.html')
    else:
        flash("Vous devez être connecté pour ajouter une note.", "danger")
        return redirect(url_for('connexion'))



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
