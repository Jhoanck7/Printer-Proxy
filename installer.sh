#!/bin/bash

# ==========================================================
#   Instalador by Jhoan-Montero - POS Proxy v1.1
#   Farmacias Galeno-Apotheca
# ==========================================================

echo "------------------------------------------------"
echo "   Iniciando instalación de POS Proxy by Jhoan ...   "
echo "------------------------------------------------"

# 1. Actualizar sistema e instalar dependencias base
echo "[1/5] Instalando dependencias del sistema (USB y Python)..."
sudo apt update
sudo apt install -y python3-pip python3-pil libusb-1.0-0-dev

# 2. Instalar librerías de Python necesarias
# Nota: Usamos --break-system-packages por la versión de Debian/Ubuntu actual
echo "[2/5] Instalando librerías Flask, ESC/POS y Pillow..."
pip3 install flask flask-cors python-escpos Pillow --break-system-packages

# 3. Configurar la Regla UDEV para la impresora (Permisos USB)
# Esto "inserta" el permiso 0666 para que no pida sudo al imprimir
echo "[3/5] Insertando regla de permisos para impresora USB..."
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", ATTR{idProduct}=="2016", MODE="0666", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/99-printer.rules

# Reiniciar el gestor de dispositivos para que reconozca la regla
sudo udevadm control --reload-rules
sudo udevadm trigger

# 4. Crear el archivo del Servicio (Systemd)
# Esto hace que el script sea un "fantasma" que corre siempre al fondo
echo "[4/5] Configurando inicio automático (Servicio)..."
USER_NAME=$(whoami)
CURRENT_DIR=$(pwd)

sudo tee /etc/systemd/system/pos_proxy.service > /dev/null <<EOF
[Unit]
Description=J&D POS Proxy Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $CURRENT_DIR/impresora_proxy.py
WorkingDirectory=$CURRENT_DIR
StandardOutput=inherit
StandardError=inherit
Restart=always
User=$USER_NAME

[Install]
WantedBy=multi-user.target
EOF

# 5. Activar y arrancar el servicio
echo "[5/5] Activando el servicio pos_proxy..."
sudo systemctl daemon-reload
sudo systemctl enable pos_proxy.service
sudo systemctl restart pos_proxy.service

echo "------------------------------------------------"
echo " ¡INSTALACIÓN COMPLETADA CON ÉXITO!"
echo "------------------------------------------------"
