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
    response = HTMLResponse(content=success_html)
    # Ce header indique à HTMX de déclencher l'événement 'expenseAdded' sur le body
    # ce qui va forcer la colonne de droite à se recharger toute seule !
    response.headers["HX-Trigger"] = "expenseAdded"
    return response


# ---------------------------------------------------------
# 4.5 ROUTE : GET /api/expenses (Historique)
# ---------------------------------------------------------
@app.get("/api/expenses")
async def get_expenses(start_date: str = "", end_date: str = "", category: str = ""):
    if not sheets_client:
        return HTMLResponse("<div class='alert alert-error'>Erreur de connexion à Google Sheets.</div>")
        
    rows = sheets_client.get_all_expenses()
    if not rows:
        return HTMLResponse("<p style='text-align: center; color: #9ca3af;'>Aucun ticket enregistré pour le moment.</p>")
        
    import datetime
    
    def format_gsheet_date(date_val):
        try:
            serial = float(date_val)
            if 30000 < serial < 60000:
                dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=serial)
                return dt.strftime("%Y-%m-%d")
        except:
            pass
        return date_val

    rows_html = ""
    
    # On associe chaque ligne à son index physique dans Google Sheets
    # La ligne 1 est l'en-tête, donc l'index de rows[0] est 2.
    rows_with_indices = [(r, idx + 2) for idx, r in enumerate(rows)]
    
    for r, sheet_row_index in reversed(rows_with_indices): 
        row_data = r + [""] * (10 - len(r))
        
        type_doc = row_data[1]
        date_str = format_gsheet_date(row_data[3])
        
        # Filtres
        if category and type_doc.lower() != category.lower():
            continue
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
            
        fournisseur = row_data[2]
        montant = row_data[4]
        devise = row_data[6]
        image_cell = row_data[9]
        
        image_link = ""
        image_cell_str = str(image_cell).strip()
        if image_cell_str.upper().startswith('=IMAGE('):
            try:
                url = image_cell_str.split('"')[1]
                image_link = f'<a href="{url}" target="_blank"><img src="{url}" alt="Reçu" style="max-height: 45px; border-radius: 4px; border: 1px solid #444; transition: transform 0.2s;"></a>'
            except: pass
        elif image_cell_str.startswith('http'):
            image_link = f'<a href="{image_cell_str}" target="_blank"><img src="{image_cell_str}" alt="Reçu" style="max-height: 45px; border-radius: 4px; border: 1px solid #444; transition: transform 0.2s;"></a>'
        
        delete_btn = f"""
        <button hx-delete="/api/expenses/{sheet_row_index}" 
                hx-confirm="Êtes-vous sûr de vouloir supprimer cette dépense de votre tableau Google Sheets ?"
                hx-target="#history-container"
                hx-include="#filter-form"
                class="delete-btn" title="Supprimer définitivement">
            ✖
        </button>
        """
        
        rows_html += f"""
        <tr>
            <td>{date_str}</td>
            <td><strong>{fournisseur}</strong></td>
            <td><span style="text-transform: capitalize;">{type_doc}</span></td>
            <td style="font-weight: bold; color: #f3f4f6;">{montant} {devise}</td>
            <td>{image_link}</td>
            <td style="text-align: center;">{delete_btn}</td>
        </tr>
        """
        
    table_html = f"""
    <div class="table-container" style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa;">Date</th>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa;">Fournisseur</th>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa;">Catégorie</th>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa;">Montant</th>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa; text-align: center;">Reçu</th>
                    <th style="padding: 12px; border-bottom: 1px solid #444; background-color: #202b3c; color: #60a5fa; text-align: center;"></th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    <style>
        .table-container table tr:hover {{ background-color: #2d2d2d; }}
        .table-container table td {{ padding: 12px; border-bottom: 1px solid #333; vertical-align: middle; }}
        .table-container table td:nth-child(5) {{ text-align: center; }}
        .table-container img:hover {{ transform: scale(1.1); }}
        .delete-btn {{ color: #ef4444; background: none; border: none; cursor: pointer; font-size: 1.2rem; transition: transform 0.2s, color 0.2s; }}
        .delete-btn:hover {{ transform: scale(1.3); color: #dc2626; }}
    </style>
    """
    return HTMLResponse(content=table_html)

@app.delete("/api/expenses/{row_index}")
async def delete_expense_route(row_index: int, start_date: str = "", end_date: str = "", category: str = ""):
    if sheets_client:
        sheets_client.delete_expense(row_index)
    # Après suppression, on renvoie la liste filtrée à jour pour remplacer le tableau via HTMX
    return await get_expenses(start_date=start_date, end_date=end_date, category=category)


from fastapi.responses import Response
import io
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:
    pass

@app.get("/api/export-pdf")
async def export_pdf(start_date: str = "", end_date: str = "", category: str = ""):
    if not sheets_client:
        raise HTTPException(status_code=500, detail="Google Sheets non connecté")
        
    rows = sheets_client.get_all_expenses()
    
    import datetime
    def format_gsheet_date(date_val):
        try:
            serial = float(date_val)
            if 30000 < serial < 60000:
                dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=serial)
                return dt.strftime("%Y-%m-%d")
        except: pass
        return str(date_val)

    filtered_data = []
    total = 0.0
    for r in reversed(rows):
        row_data = r + [""] * (10 - len(r))
        type_doc = row_data[1]
        date_str = format_gsheet_date(row_data[3])
        
        if category and type_doc.lower() != category.lower(): continue
        if start_date and date_str < start_date: continue
        if end_date and date_str > end_date: continue
        
        fournisseur = row_data[2]
        montant_str = row_data[4]
        try:
            total += float(montant_str.replace(',', '.'))
        except: pass
        devise = row_data[6]
        
        filtered_data.append((date_str, fournisseur, type_doc.capitalize(), f"{montant_str} {devise}"))

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 800, "Devis de Depenses (Expense Tracker IA)")
    
    p.setFont("Helvetica", 10)
    p.drawString(50, 780, f"Filtres - Categorie: {category or 'Toutes'} | Du: {start_date or '-'} Au: {end_date or '-'}")
    
    y = 750
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Date")
    p.drawString(150, y, "Fournisseur")
    p.drawString(350, y, "Categorie")
    p.drawString(450, y, "Montant")
    
    p.setFont("Helvetica", 11)
    y -= 20
    for item in filtered_data:
        p.drawString(50, y, str(item[0]))
        p.drawString(150, y, str(item[1])[:30])
        p.drawString(350, y, str(item[2]))
        p.drawString(450, y, str(item[3]))
        y -= 20
        if y < 50:
            p.showPage()
            p.setFont("Helvetica", 11)
            y = 800
            
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y - 20, f"Total estimatif : {total:.2f}")
    
    p.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    headers = {'Content-Disposition': 'attachment; filename="devis_depenses.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

@app.get("/api/export-csv")
async def export_csv(start_date: str = "", end_date: str = "", category: str = ""):
    if not sheets_client:
        raise HTTPException(status_code=500, detail="Google Sheets non connecté")
        
    rows = sheets_client.get_all_expenses()
    
    import datetime
    def format_gsheet_date(date_val):
        try:
            serial = float(date_val)
            if 30000 < serial < 60000:
                dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=serial)
                return dt.strftime("%Y-%m-%d")
        except: pass
        return str(date_val)

    csv_content = "Date,Fournisseur,Categorie,Montant,Devise,Description\n"
    
    for r in reversed(rows):
        row_data = r + [""] * (10 - len(r))
        type_doc = row_data[1]
        date_str = format_gsheet_date(row_data[3])
        
        if category and type_doc.lower() != category.lower(): continue
        if start_date and date_str < start_date: continue
        if end_date and date_str > end_date: continue
        
        # Echapper les guillemets pour le CSV
        fournisseur = row_data[2].replace('"', '""')
        montant = row_data[4]
        devise = row_data[6]
        desc = row_data[7].replace('"', '""')
        
        csv_content += f'"{date_str}","{fournisseur}","{type_doc}","{montant}","{devise}","{desc}"\n'
        
    headers = {'Content-Disposition': 'attachment; filename="notes_de_frais.csv"'}
    # Assurer le formatage UTF-8 avec BOM pour une ouverture facile dans Excel
    return Response(content="\ufeff" + csv_content, media_type="text/csv; charset=utf-8", headers=headers)
