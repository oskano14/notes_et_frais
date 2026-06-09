# 🧾 Expense Tracker IA

## 🎯 Contexte et But de l'Application

**Expense Tracker IA** est une application web conçue pour automatiser la gestion et la saisie des notes de frais. 
Grâce à un modèle d'Intelligence Artificielle de vision (via l'API Groq), l'application est capable d'analyser instantanément la photo d'un ticket de caisse ou d'une facture, d'en extraire les informations clés (montant, TVA, fournisseur, date, type de dépense), et de les préparer pour validation.

Une fois les données vérifiées par l'utilisateur via une interface moderne et fluide (HTMX / Vanilla JS), l'application :
1. **Sauvegarde l'image** du reçu sur le cloud de manière sécurisée (via Cloudinary).
2. **Ajoute une nouvelle ligne** dans un tableau de suivi Google Sheets avec les détails de la dépense et la miniature de l'image.

---

## 📂 Structure du Projet

```text
expense-tracker/
├── app.py                  # Serveur web FastAPI (Routes, gestion HTMX)
├── backend.py              # Logique d'Intelligence Artificielle (Groq, LLaMA Vision)
├── sheets.py               # Connecteurs API Google Sheets & Cloudinary
├── test.py                 # Script de test global en ligne de commande
├── requirements.txt        # Liste des dépendances Python
├── .env                    # Fichier (à créer) contenant les clés d'API (non versionné)
├── .env.example            # Template d'exemple pour les variables d'environnement
├── prompt.txt              # Le prompt détaillé pour guider l'IA
├── job-ia-...json          # (Local) Fichier d'identification du Compte de Service Google Cloud
└── static/                 # Ressources Front-End
    ├── index.html          # Page principale avec HTML & CSS Dark Mode intégré
    └── app.js              # Script gérant la prévisualisation et l'interactivité
```

---

## 🛠️ Étapes d'Installation

### 1. Accéder au dossier du projet
Si vous venez de récupérer le code source :
```bash
cd expense-tracker
```

### 2. Créer un environnement virtuel et installer les dépendances
Il est fortement recommandé d'utiliser un environnement virtuel (`venv`) pour isoler les bibliothèques :
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurer le fichier `.env`
Dupliquez le fichier `.env.example` en le renommant `.env` (ou créez-le manuellement) :
```bash
cp .env.example .env
```
Complétez les variables à l'intérieur de votre `.env` :
- `GROQ_API_KEY` : Votre clé API Groq pour l'intelligence artificielle.
- `GOOGLE_SHEET_ID` : L'identifiant de votre document Google Sheets (trouvable dans l'URL du fichier).
- `GOOGLE_SERVICE_ACCOUNT_JSON` : Le chemin vers le fichier JSON de votre compte de service Google.
- `CLOUDINARY_URL` : Votre URL Cloudinary au format `cloudinary://API_KEY:API_SECRET@CLOUD_NAME`.

### 4. Lancer l'application
Démarrez le serveur FastAPI avec le mode rechargement à chaud :
```bash
uvicorn app:app --reload
```
Le projet est désormais accessible depuis votre navigateur à l'adresse : **[http://127.0.0.1:8000](http://127.0.0.1:8000)** !

---

## ☁️ Configuration Google Cloud & Cloudinary

### Google Cloud (Google Sheets)
Pour que l'application puisse écrire dans votre tableur :
1. Rendez-vous sur la **Google Cloud Console**, créez un projet et activez l'**API Google Sheets**.
2. Créez un **Compte de service** (Service Account) et générez une clé d'accès au format **JSON**.
3. Placez ce fichier JSON dans le dossier de votre projet et pointez vers lui avec la variable `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. **Étape cruciale** : Allez sur votre fichier Google Sheets et **partagez-le en tant qu'"Éditeur"** avec l'adresse email générée par votre Compte de service (ex: `agent-xxx@nom-projet.iam.gserviceaccount.com`). Sans cela, l'application n'aura pas la permission de modifier le fichier.

### Cloudinary (Hébergement des images)
Pour éviter les limitations de quota imposées par Google Drive sur les comptes de service :
1. Créez un compte gratuit sur [Cloudinary](https://cloudinary.com).
2. Sur votre tableau de bord, copiez la variable d'environnement `CLOUDINARY_URL` et ajoutez-la à votre fichier `.env`.
3. Cloudinary hébergera vos tickets de caisse de façon sécurisée et générera l'URL utilisée par Google Sheets pour afficher la miniature.

---

## 🤖 Exemple de JSON retourné par le modèle (IA)

Notre agent IA, utilisant LLaMA via Groq, analyse l'image et retourne une structure stricte au format JSON (imposée via le mode JSON). 
Voici un exemple typique du résultat obtenu après l'analyse d'un reçu de restaurant :

```json
{
  "horodatage": "20:45",
  "type": "restaurant",
  "fournisseur": "Grand Lux Cafe",
  "date": "2023-11-22",
  "montant_ttc": 69.25,
  "tva": 11.54,
  "devise": "USD",
  "description": "Repas d'affaires avec les clients, dîner au restaurant.",
  "confiance": "haute"
}
```
Ce JSON est ensuite capturé par notre serveur (FastAPI), qui s'en sert pour générer dynamiquement le formulaire de validation interactif que vous voyez sur l'interface !
