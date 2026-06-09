import os
import json
import base64
from dotenv import load_dotenv
from groq import Groq

class ExpenseAgent:
    """Classe ExpenseAgent — logique IA"""
    def __init__(self):
        load_dotenv()
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def extract_from_bytes(self, image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
        """
        Envoie l'image au modèle Vision de Groq pour en extraire les informations.
        """
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        context_path = os.path.join(base_dir, "context.txt")
        prompt_path = os.path.join(base_dir, "prompt.txt")
        
        # 3. On appelle le modèle Llama 4 vision via Groq
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": self.read_file(context_path)
                },
                {
                    "role": "user",
                    "content": [
                        # On injecte le texte de la consigne (prompt.txt)
                        {"type": "text", "text": self.read_file(prompt_path)},
                        # On injecte l'image sous forme d'URL Base64
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            # On force le modèle à retourner uniquement du JSON valide
            response_format={"type": "json_object"},
            model="meta-llama/llama-4-scout-17b-16e-instruct" 
        )

        # 4. Parsing de la réponse JSON retournée par le modèle
        response_content = chat_completion.choices[0].message.content
        try:
            # On transforme la chaîne JSON en dictionnaire Python
            extracted_data = json.loads(response_content)
        except json.JSONDecodeError:
            extracted_data = {}

        # 5. Validation et sécurisation des clés
        # L'énoncé demande de valider que tous les champs sont présents pour ne pas faire planter le frontend
        expected_fields = [
            "horodatage", "type", "fournisseur", "date", "montant_ttc", 
            "tva", "devise", "description", "confiance", "image"
        ]
        
        for field in expected_fields:
            # Si le modèle a oublié de renvoyer une clé, on l'ajoute nous-mêmes avec la valeur None (null)
            if field not in extracted_data:
                extracted_data[field] = None
                
        return extracted_data

if __name__ == "__main__":
    
    agent = ExpenseAgent()
    test_image_path = "ticket_test.jpg" 
    
    if os.path.exists(test_image_path):
        print(f"Analyse de l'image {test_image_path} en cours (cela peut prendre quelques secondes)...")
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        result = agent.extract_from_bytes(image_bytes, "image/jpeg")
        
        # Affichage du résultat JSON formaté de manière lisible
        print("\n--- RÉSULTAT EXTRAIT ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("------------------------")
    else:
        print(f"❌ Impossible de tester : L'image '{test_image_path}' n'a pas été trouvée dans le dossier.")
        print("Veuillez ajouter une image avec ce nom dans le dossier expense-tracker et relancer.")
