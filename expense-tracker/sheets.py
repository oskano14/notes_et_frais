import os
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

class GoogleSheetsClient:
    """Classe GoogleSheetsClient — intégration GSheet et Google Drive"""
    
    def __init__(self):
        # Charge les variables d'environnement (.env)
        load_dotenv(override=True)
        
        # Récupération des ID et chemins depuis le .env
        self.sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        self.credentials_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.drive_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        
        # Scopes autorisés : on a besoin d'accéder aux tableurs et au drive
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 1. Validation du fichier de credentials
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Le fichier JSON du compte de service est introuvable au chemin : {self.credentials_path}")
            
        # 2. Création de l'objet d'authentification global
        self.credentials = Credentials.from_service_account_file(
            self.credentials_path, 
            scopes=self.scopes
        )
        
        # 3. Initialisation du client GSpread (pour Google Sheets)
        self.gspread_client = gspread.authorize(self.credentials)
        
        # 4. Ouverture du document et de la feuille "Notes de frais"
        try:
            self.spreadsheet = self.gspread_client.open_by_key(self.sheet_id)
            self.worksheet = self.spreadsheet.worksheet("Notes de frais")
        except Exception as e:
            print(f"❌ Erreur critique lors de l'ouverture du Google Sheet (ID: {self.sheet_id}).")
            print("Vérifiez que cet ID est bien une clé de sheet et que le compte de service y a accès.")
            raise e
            
        # 5. Initialisation du client Google Drive (pour l'upload des images)
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
        
    def upload_image_to_drive(self, image_path: str) -> str:
        """
        Upload une image sur le Drive du compte de service, 
        la rend publique, et retourne son URL.
        """
        if not hasattr(self, 'drive_folder_id') or not self.drive_folder_id:
            print("      ⚠️ [Info] GOOGLE_DRIVE_FOLDER_ID n'est pas configuré dans le .env.")
            print("      ⚠️ [Info] L'upload de l'image est ignoré pour éviter l'erreur de quota.")
            return None
            
        if not os.path.exists(image_path):
            print(f"⚠️ Image introuvable pour l'upload : {image_path}")
            return None
            
        # Nom qu'aura le fichier dans le Drive
        file_metadata = {
            'name': os.path.basename(image_path)
        }
        # Si un dossier cible est précisé, on place l'image dedans (contourne l'erreur de quota)
        if hasattr(self, 'drive_folder_id') and self.drive_folder_id:
            file_metadata['parents'] = [self.drive_folder_id]
        
        # Media object (le fichier lui-même)
        media = MediaFileUpload(image_path, resumable=True)
        
        try:
            # ÉTAPE A : Uploader le fichier
            uploaded_file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink, webViewLink' # On demande à l'API de nous retourner ces 3 infos
            ).execute()
        except Exception as e:
            print(f"\n      ⚠️ Impossible d'uploader sur Drive (limitation Google) : {e}")
            print("      ⚠️ L'image sera ignorée, mais les données seront quand même envoyées au tableur.")
            return None
            
        file_id = uploaded_file.get('id')
        
        # ÉTAPE B : Modifier les permissions pour le rendre "public via le lien"
        permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        self.drive_service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        
        # Retourner l'URL webContentLink (qui permet un téléchargement direct/affichage)
        # ou webViewLink (page de visualisation Google Drive). 
        # Pour =IMAGE("url"), webContentLink fonctionne parfois mieux.
        return uploaded_file.get('webContentLink', uploaded_file.get('webViewLink'))

    def append_expense(self, data: dict, image_url: str = None):
        """
        Ajoute une ligne au Google Sheet "Notes de frais".
        """
        # Si on a une URL, on utilise la formule de tableur =IMAGE()
        image_cell_content = f'=IMAGE("{image_url}")' if image_url else ""
        
        # Construction de la ligne dans l'ordre de vos colonnes :
        # Horodatage | Type | Fournisseur | Date | Montant TTC | TVA | Devise | Description | Confiance | Image
        row = [
            data.get("horodatage", ""),
            data.get("type", ""),
            data.get("fournisseur", ""),
            data.get("date", ""),
            data.get("montant_ttc", ""),
            data.get("tva", ""),
            data.get("devise", ""),
            data.get("description", ""),
            data.get("confiance", ""),
            image_cell_content
        ]
        
        # Ajout de la ligne avec value_input_option='USER_ENTERED' 
        # (indispensable pour que =IMAGE() soit reconnu comme une formule et non du texte simple)
        self.worksheet.append_row(row, value_input_option='USER_ENTERED')
        return True


# ==========================================
# SCRIPT DE TEST ISOLÉ (Étape 3.2)
# ==========================================
if __name__ == "__main__":
    print("⏳ Tentative de connexion à Google Sheets et Drive...")
    try:
        # L'instanciation vérifie les credentials et tente d'ouvrir le fichier
        client = GoogleSheetsClient()
        print("✅ Connexion réussie ! Le fichier et la feuille ont été trouvés.")
        
        # Création d'une donnée factice pour valider l'écriture
        fake_data = {
            "horodatage": "12:00",
            "type": "Test Automatique",
            "fournisseur": "MonBot Python",
            "date": "2026-06-09",
            "montant_ttc": 13.37,
            "tva": 2.67,
            "devise": "EUR",
            "description": "Validation du TP : la ligne s'insère bien !",
            "confiance": "haute"
        }
        
        print("⏳ Insertion de la ligne factice dans la feuille 'Notes de frais'...")
        client.append_expense(fake_data)
        print("✅ SUCCÈS ! Allez vérifier dans votre Google Sheet, une nouvelle ligne a dû apparaître.")
        
    except Exception as e:
        print("\n❌ L'écriture ou la connexion a échoué. Voici l'erreur :")
        print(str(e))
