from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from escpos.printer import Usb
import time
import base64
from io import BytesIO
from PIL import Image
import os
from dotenv import load_dotenv
from usb.util import dispose_resources


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
def formato_moneda(numero):
    """Convierte un número a string con puntos de miles: 1500 -> 1.500"""
    try:
        # El :, usa la coma como separador de miles estándar de Python
        # Luego reemplazamos esa coma por un punto para el formato chileno
        return "{:,}".format(int(numero)).replace(",", ".")
    except:
        return str(numero)
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
    print(f"Conectado a la impresora {hex(VENDOR_ID)}:{hex(PRODUCT_ID)}")
    
    if not p:
        return jsonify({"status": "error", "message": "Impresora no encontrada"}), 500


    try:
        p.hw("init")
        
        # --- 1. LOGO ---
        if os.path.exists(PATH_LOGO):
            try:
                img_logo = Image.open(PATH_LOGO).convert('L')
                img_logo.thumbnail((400, 400)) # Un poco más grande para 80mm
                p.set(align='center')
                p.image(img_logo)
            except: pass

        # --- 2. ENCABEZADO ---
        p.set(align='center', bold=True)
        p.text(f"{datos.get('company_name', 'FARMACIAS APOTHECA').upper()}\n")
        p.set(align='center', bold=False)
        p.text(f"{datos.get('company_location', '')}\n")
        p.text(f"{datos.get('company_city', '')}\n\n")

        # --- 3. RECUADRO LEGAL (48 CARACTERES) ---
        # El cuadro ahora mide 40 caracteres para dejar margen a los lados
        p.set(align='center', bold=True)
        p.text("" + "-"*40 + "\n")
        p.text(f"RUT:{datos.get('company_rut', '')} \n")
        p.text(f" {datos.get('document_type', '')} \n")
        p.text(f"Nº: {datos.get('voucher_number', '')} \n")
        p.text("" + "-"*40 + "\n\n\n\n")

        # --- 4. INFO VENTA ---
        p.set(align='left', bold=False)
        # Usamos :<15 para la etiqueta y el resto para el dato
        p.text(f"{'FECHA:':<15}{datos.get('date', ''):<33}\n")
        p.text(f"{'LOCAL:':<15}{datos.get('office', ''):<33}\n")
        p.text(f"{'VENDEDOR:':<15}{datos.get('cashier', ''):<33}\n")
        p.text("-" * 48 + "\n")
        
        p.text(f"{'CLIENTE:':<15}{datos.get('cliente_nombre', 'Consumidor Final'):<33}\n")
        p.text(f"{'RUT:':<15}{datos.get('cliente_rut', '66.666.666-6'):<33}\n")
        p.text("-" * 48 + "\n")

        # --- 5. DETALLE DE PRODUCTOS (ANCHO 48) ---
        p.set(align='left', bold=True)
        # 34 espacios para descripción, 14 para el total
        p.text(f"{'DESCRIPCION':<34}{'TOTAL':>14}\n")
        p.set(bold=False)
        
        for l in datos.get('lines', []):
            # Si el nombre es muy largo, lo cortamos a 48 para que no rompa la línea
            desc = l['desc'][:48] 
            qty_price = f"   {l['qty']} x {l['price']}"
            p.text(f"{desc:<48}\n") 
            p.text(f"{qty_price:<34}{l['total']:>14}\n")
            
        p.text("-" * 48 + "\n")
        
        # --- 6. TOTALES ---
        total_int = int(datos.get('total', 0))
        neto = round(total_int / 1.19)
        iva = total_int - neto
        
        p.set(align='right')
        # Alineamos los montos a la derecha dentro de un bloque de 20 caracteres
        p.text(f"{'MONTO NETO:':<20}{'$':>11}{formato_moneda(neto):>10}\n")
        p.text(f"{'IVA 19%:':<20}{'$':>11}{formato_moneda(iva):>10}\n")
        
        p.set(align='right', bold=True, width=2, height=2)
        p.text(f"TOTAL: $ {formato_moneda(total_int)}\n")
        p.set(width=1, height=1)
        p.text("-" * 48 + "\n")

        # --- 7. TIMBRE SII ---
        sii_b64 = datos.get('sii_barcode')
        if sii_b64:
            try:
                if "," in sii_b64: sii_b64 = sii_b64.split(",")[1]
                img_data = base64.b64decode(sii_b64)
                sii_img = Image.open(BytesIO(img_data)).convert('L')
                
                # AUMENTO DE TAMAÑO: Redimensionamos la imagen antes de imprimir
                # El ancho estándar para 80mm es aprox 500-550 píxeles para que se vea imponente
                ancho_timbre = 520 
                w_percent = (ancho_timbre / float(sii_img.size[0]))
                h_size = int((float(sii_img.size[1]) * float(w_percent)))
                sii_img = sii_img.resize((ancho_timbre, h_size), Image.NEAREST)

                # Umbral de blanco y negro para máxima nitidez del escáner
                sii_img = sii_img.point(lambda x: 0 if x < 128 else 255, '1')
                
                p.set(align='center')
                # Usamos fragmentos más grandes para el buffer de la impresora
                p.image(sii_img, impl='bitImageRaster') 
                
                p.set(align='center', bold=True)
                p.text("\nTIMBRE ELECTRONICO SII\n")
                p.text("Verifique documento en www.sii.cl\n")
            except Exception as e:
                print(f"Error en timbre: {e}")

                
        # --- 8. PIE DE PAGINA ---
        p.set(align='center', bold=False)
        if datos.get('resolution_number'):
            p.text(f"Resolucion SII Nro {datos['resolution_number']}\n")
            p.text(f"Fecha: {datos['resolution_date']}\n")
        
        p.text("\n*** GRACIAS POR SU COMPRA ***\n")
        p.text(f"ID EMISION: {datos.get('name')}\n")
        
        # Espacio para el corte
        p.text("\n\n\n\n") 
        p.cut()

        dispose_resources(p.device)
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Mantener puerto 8080 como en tu script
    app.run(host='0.0.0.0', port=8080, debug=False)