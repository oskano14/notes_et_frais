document.addEventListener("DOMContentLoaded", function() {
    const fileInput = document.getElementById("file-input");
    const previewContainer = document.getElementById("preview-container");
    const imagePreview = document.getElementById("image-preview");
    const dropZone = document.getElementById("drop-zone");
    const resetBtn = document.getElementById("reset-btn");
    const analyzeBtn = document.getElementById("analyze-btn");
    const confirmationContainer = document.getElementById("confirmation-container");

    // 1. Capture ou upload d'image avec prévisualisation
    fileInput.addEventListener("change", function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(evt) {
                // Met à jour la source de l'image
                imagePreview.src = evt.target.result;
                
                // Bascule l'affichage (cache la zone d'upload, montre l'image et le bouton analyser)
                previewContainer.style.display = "block";
                dropZone.style.display = "none";
                analyzeBtn.style.display = "block";
                
                // Vider les anciens résultats s'il y en a
                confirmationContainer.innerHTML = ""; 
            }
            reader.readAsDataURL(file);
        }
    });

    // 5. Réinitialisation : bouton pour recommencer avec une nouvelle photo
    resetBtn.addEventListener("click", function() {
        fileInput.value = ""; // Vider l'input file
        previewContainer.style.display = "none";
        dropZone.style.display = "block";
        analyzeBtn.style.display = "none";
        confirmationContainer.innerHTML = "";
    });
    
    // Gérer l'état des boutons pendant les requêtes HTMX pour une meilleure UX
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        // Désactiver le bouton d'analyse pour éviter les clics multiples
        if(evt.detail.elt.id === "upload-form") {
            analyzeBtn.disabled = true;
            analyzeBtn.innerText = "Analyse...";
        }
        
        // Désactiver le bouton de validation finale
        if(evt.detail.target.id === "confirmation-container" && evt.detail.elt.tagName !== "FORM" && evt.detail.elt.id !== "upload-form") {
            const submitBtns = document.querySelectorAll('#confirmation-container button[type="submit"]');
            submitBtns.forEach(btn => {
                btn.disabled = true;
                btn.innerText = "Envoi...";
            });
        }
    });

    document.body.addEventListener('htmx:afterRequest', function(evt) {
        // Restaurer le bouton d'analyse quand la requête se termine
        if(evt.detail.elt.id === "upload-form") {
            analyzeBtn.disabled = false;
            analyzeBtn.innerText = "Analyser le reçu";
            // On cache le bouton d'analyse car on passe à l'étape du formulaire
            if(evt.detail.successful) {
                analyzeBtn.style.display = "none";
            }
        }
    });
});
