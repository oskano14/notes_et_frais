import os
import base64
import tempfile
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from backend import ExpenseAgent
from sheets import GoogleSheetsClient

app = FastAPI()

# ---------------------------------------------------------
# INITIALISATION DES SERVICES
# ---------------------------------------------------------
try:
    print("⏳ Initialisation de ExpenseAgent (Groq)...")
    agent = ExpenseAgent()
    print("⏳ Initialisation de GoogleSheetsClient...")
    sheets_client = GoogleSheetsClient()
    print("✅ Services prêts.")
except Exception as e:
    print(f"❌ Erreur critique au démarrage : {e}")
    agent = None
    sheets_client = None

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------
# 4.4 GESTIONNAIRE D'ERREURS GLOBAL (Dark Mode)
# ---------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    html_content = f"""
    <div class="alert alert-error">
        <h4 style="margin-top:0;">❌ Une erreur est survenue</h4>
        <p style="margin-bottom:0;">{str(exc)}</p>
    </div>
    """
    return HTMLResponse(content=html_content, status_code=500)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    html_content = f"""
    <div class="alert alert-error">
        <h4 style="margin-top:0;">⚠️ Erreur de validation</h4>
        <p style="margin-bottom:0;">{exc.detail}</p>
    </div>
    """
    return HTMLResponse(content=html_content, status_code=exc.status_code)


# ---------------------------------------------------------
# 4.1 ROUTE : GET /
# ---------------------------------------------------------
@app.get("/")
async def serve_index():
    index_path = "static/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return HTMLResponse("<h1>Fichier static/index.html introuvable.</h1>", status_code=404)


# ---------------------------------------------------------
# 4.2 ROUTE : POST /api/analyze
# ---------------------------------------------------------
@app.post("/api/analyze")
async def analyze_receipt(file: UploadFile = File(...)):
    if not agent:
        raise Exception("L'agent IA n'est pas initialisé.")
        
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier envoyé n'est pas une image.")
        
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="L'image dépasse 10 Mo.")
        
    data = agent.extract_from_bytes(image_bytes, file.content_type)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # Générateur de champs pour s'adapter au Dark Mode CSS
    def make_input(label, name, value, type="text"):
        val = value if value is not None else ""
        if name == "type":
            options = ["restaurant", "transport", "logement", "fourniture", "autre"]
            options_html = ""
            for opt in options:
                selected = 'selected' if val.lower() == opt else ''
                options_html += f'<option value="{opt}" {selected}>{opt.capitalize()}</option>'
            return f"""
            <div class="form-group">
                <label>{label}</label>
                <select name="{name}" class="form-control">
                    {options_html}
                </select>
            </div>
            """
        return f"""
        <div class="form-group">
            <label>{label}</label>
            <input type="{type}" name="{name}" value="{val}" class="form-control" />
        </div>
        """

    # 2. Formulaire d'édition : apparaît après analyse, avec les classes Dark Mode
    form_html = f"""
    <div style="margin-top: 30px; border-top: 1px solid #333; padding-top: 20px;">
        <h2 style="margin-top:0; color: #fff;">📋 Formulaire d'édition</h2>
        <p style="color: #9ca3af; font-size: 0.9em;">Vérifiez et complétez les données avant l'envoi.</p>
        
        <!-- 3. Soumission vers /api/submit -->
        <form hx-post="/api/submit" hx-target="#confirmation-container" hx-swap="innerHTML" hx-indicator="#submit-loading">
            {make_input("Fournisseur", "fournisseur", data.get("fournisseur"))}
            
            <div class="flex-row">
                <div class="flex-col">{make_input("Montant TTC", "montant_ttc", data.get("montant_ttc"), "number")}</div>
                <div class="flex-col">{make_input("TVA", "tva", data.get("tva"), "number")}</div>
                <div class="flex-col">{make_input("Devise", "devise", data.get("devise"))}</div>
            </div>
            
            <div class="flex-row">
                <div class="flex-col">{make_input("Date", "date", data.get("date"), "date")}</div>
                <div class="flex-col">{make_input("Type de document", "type", data.get("type"))}</div>
            </div>
            
            {make_input("Description", "description", data.get("description"))}
            
            <!-- Champ caché Base64 -->
            <input type="hidden" name="image_base64" value="{image_base64}" />
            <input type="hidden" name="horodatage" value="{data.get('horodatage', '')}" />
            <input type="hidden" name="confiance" value="{data.get('confiance', '')}" />
            
            <button type="submit" class="btn btn-success">
                Envoyer vers le Google Sheet
            </button>
            <div id="submit-loading" class="htmx-indicator">
                ⏳ Upload sur Cloudinary et Google Sheets en cours...
            </div>
        </form>
    </div>
    """
    return HTMLResponse(content=form_html)


# ---------------------------------------------------------
# 4.3 ROUTE : POST /api/submit
# ---------------------------------------------------------
@app.post("/api/submit")
async def submit_receipt(
    fournisseur: str = Form(""),
    montant_ttc: str = Form(""),
    tva: str = Form(""),
    devise: str = Form(""),
    date: str = Form(""),
    horodatage: str = Form(""),
    type: str = Form(""),
    description: str = Form(""),
    confiance: str = Form(""),
    image_base64: str = Form("")
):
    if not sheets_client:
        raise Exception("GoogleSheetsClient n'est pas prêt.")

    data = {
        "horodatage": horodatage,
        "type": type,
        "fournisseur": fournisseur,
        "date": date,
        "montant_ttc": montant_ttc,
        "tva": tva,
        "devise": devise,
        "description": description,
        "confiance": confiance
    }
    
    image_url = None
    if image_base64:
        image_bytes = base64.b64decode(image_base64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name
            
        try:
            image_url = sheets_client.upload_image_to_cloudinary(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    sheets_client.append_expense(data, image_url)
    
    # 4. Confirmation (succès ou échec via gestionnaire d'erreur)
    success_html = f"""
    <div class="alert alert-success">
        <h3 style="margin-top:0;">✅ Dépense enregistrée avec succès !</h3>
        <p><strong>{fournisseur}</strong> : {montant_ttc} {devise}</p>
        <p style="font-size: 0.9em; margin-bottom: 20px;">L'image et les données ont été sauvegardées.</p>
        
        <button onclick="location.reload()" class="btn btn-outline">
            📝 Enregistrer une nouvelle facture
        </button>
    </div>
    """
    return HTMLResponse(content=success_html)
