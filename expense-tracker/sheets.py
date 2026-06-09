import os
from dotenv import load_dotenv
load_dotenv(override=True)

import gspread
from google.oauth2.service_account import Credentials
import cloudinary
import cloudinary.uploader

class GoogleSheetsClient:
    """Classe GoogleSheetsClient — intégration GSheet et Cloudinary"""
    
    def __init__(self):
        # Charge les variables d'environnement (.env)
        load_dotenv(override=True)
        
        # Récupération des ID et chemins depuis le .env
        self.sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        self.credentials_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        # Scopes autorisés : on a besoin d'accéder aux tableurs
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets"
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
            
        # 5. Cloudinary est automatiquement configuré si CLOUDINARY_URL est présent dans le .env
        
    def upload_image_to_cloudinary(self, image_path: str) -> str:
        """
        Upload une image sur Cloudinary et retourne son URL sécurisée.
        """
        if not os.path.exists(image_path):
            print(f"⚠️ Image introuvable pour l'upload : {image_path}")
            return None
            
        try:
            # ÉTAPE A : Uploader le fichier sur Cloudinary
            response = cloudinary.uploader.upload(image_path)
            # Retourner l'URL publique de l'image stockée
            return response.get("secure_url")
        except Exception as e:
            print(f"\n      ⚠️ Impossible d'uploader sur Cloudinary : {e}")
            print("      ⚠️ Assurez-vous d'avoir bien configuré CLOUDINARY_URL dans le .env.")
            return None

    def append_expense(self, data: dict, image_url: str = None):
        """
        Ajoute une ligne au Google Sheet "Notes de frais".
        """
        # Si on a une URL, on utilise la formule de tableur =IMAGE()
        image_cell_content = f'=IMAGE("{image_url}")' if image_url else ""
        
        # Construction de la ligne dans l'ordre de vos colonnes :
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
        self.worksheet.append_row(row, value_input_option='USER_ENTERED')
        return True


# ==========================================
# SCRIPT DE TEST ISOLÉ
# ==========================================
if __name__ == "__main__":
    print("⏳ Tentative de connexion à Google Sheets...")
    try:
        client = GoogleSheetsClient()
        print("✅ Connexion réussie ! Le fichier et la feuille ont été trouvés.")
        
        fake_data = {
            "horodatage": "12:00",
            "type": "Test Automatique",
            "fournisseur": "CloudinaryBot Python",
            "date": "2026-06-09",
            "montant_ttc": 13.37,
            "tva": 2.67,
            "devise": "EUR",
            "description": "Validation Cloudinary : la ligne s'insère bien !",
            "confiance": "haute"
        }
        
        print("⏳ Insertion de la ligne factice dans la feuille 'Notes de frais'...")
        client.append_expense(fake_data)
        print("✅ SUCCÈS ! Allez vérifier dans votre Google Sheet.")
        
    except Exception as e:
        print("\n❌ L'écriture ou la connexion a échoué. Voici l'erreur :")
        print(str(e))
