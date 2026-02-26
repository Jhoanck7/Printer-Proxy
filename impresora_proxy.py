from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from escpos.printer import Usb
import time
import base64
from io import BytesIO
from PIL import Image
import os
from dotenv import load_dotenv


# Cargar las variables del archivo .env
load_dotenv()
# --- RUTAS DINÁMICAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Asegúrate de que este archivo exista en la misma carpeta que el script
PATH_LOGO = os.path.join(BASE_DIR, "farmacias_apotheca.png")

app = Flask(__name__)
CORS(app, supports_credentials=True)
print(os.getenv('PRINTER_VENDOR_ID'),os.getenv('PRINTER_PRODUCT_ID'))

# IDs de la Printer-80
VENDOR_ID = int(os.getenv('PRINTER_VENDOR_ID'), 16)
PRODUCT_ID = int(os.getenv('PRINTER_PRODUCT_ID'), 16)

def conectar_impresora():
    """Intenta conectar por los canales comunes de la Printer-80"""
    for canal in [0x03, 0x02, 0x01]:
        try:
        
            return Usb(VENDOR_ID, PRODUCT_ID, out_ep=canal)
        except:
            continue
    return None

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route('/imprimir_directo', methods=['POST', 'OPTIONS'])
def imprimir():
    if request.method == 'OPTIONS': 
        return make_response()
    
    datos = request.json
    p = conectar_impresora()
    print(f"Conectado a la impresora {hex(Vendor_ID)}:{hex(PRODUCT_ID)}")
    
    if not p:
        return jsonify({"status": "error", "message": "Impresora no encontrada"}), 500


    try:
        p.hw("init")
        
        # --- 1. LOGO DEL LOCAL ---
        if os.path.exists(PATH_LOGO):
            try:
                img_logo = Image.open(PATH_LOGO).convert('L')
                img_logo.thumbnail((380, 380))
                p.set(align='center')
                p.image(img_logo)
            except: pass

        # --- 2. DATOS DEL EMISOR (EL LOCAL) ---
        p.set(align='center', bold=True)
        p.text(f"{datos.get('company_name', 'FARMACIA GALENO')}\n")
        p.set(align='center', bold=False)
        p.text(f"RUT: {datos.get('company_rut', '')}\n")
        p.text(f"{datos.get('company_location', '')}\n")
        p.text(f"{datos.get('company_city', '')}\n")
        p.text("-" * 32 + "\n")

        # --- 3. TIPO DE DOCUMENTO ---
        p.set(align='center', bold=True, width=2, height=2)
        p.text(f"{datos.get('document_type')}\n")
        p.set(align='center', width=1, height=1)
        p.text(f"NRO EMISION: {datos.get('name')}\n")
        if datos.get('voucher_number'):
            p.text(f"VOUCHER: {datos.get('voucher_number')}\n")
        p.text("-" * 32 + "\n")

        # --- 4. DATOS DEL CLIENTE (RECEPTOR) ---
        p.set(align='left', bold=False)
        p.text(f"RUT: {datos.get('cliente_rut', '66.666.666-6')}\n")
        p.text(f"NOM: {datos.get('cliente_nombre', 'Consumidor Final')}\n")
        if datos.get('cliente_email'):
            p.text(f"MAIL: {datos.get('cliente_email')}\n")
        p.text("-" * 32 + "\n")

        # --- 5. DETALLE DE PRODUCTOS ---
        for l in datos.get('lines', []):
            p.set(align='left')
            p.text(f"{l['qty']} x {l['desc'][:22]}\n")
            p.set(align='right')
            p.text(f"{l['total']}\n")
            
        p.set(align='center')
        p.text("-" * 32 + "\n")

        # --- 6. TOTAL ---
        p.set(align='right', bold=True, width=1, height=2)
        p.text(f"TOTAL: ${datos.get('total')}\n\n")

        # --- 7. TIMBRE SII ---
        sii_b64 = datos.get('sii_barcode')
        if sii_b64:
            try:
                if "," in sii_b64: sii_b64 = sii_b64.split(",")[1]
                img_data = base64.b64decode(sii_b64)
                sii_img = Image.open(BytesIO(img_data)).convert('L')
                sii_img = sii_img.point(lambda x: 0 if x < 128 else 255, '1')
                p.set(align='center')
                p.image(sii_img)
                p.text("TIMBRE ELECTRONICO SII\n")
            except: pass

        # --- 8. PIE DE PAGINA LEGAL Y LARGO ---
        p.set(align='center', bold=False)
        if datos.get('resolution_number'):
            p.text(f"\nResolucion SII Nro {datos['resolution_number']}\n")
            p.text(f"Fecha: {datos['resolution_date']}\n")
        
        p.text("\n*** GRACIAS POR PREFERIRNOS ***\n")
        # EL TOQUE FINAL: Boleta más larga (feed de papel)
        p.text("\n\n\n\n\n\n") 
        p.cut()
        
        from usb.util import dispose_resources
        dispose_resources(p.device)
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Mantener puerto 8080 como en tu script
    app.run(host='0.0.0.0', port=8080, debug=False)