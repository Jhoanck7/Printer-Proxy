#!/bin/bash

# --- Configuración de Estilo ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  INSTALADOR POS PROXY - by Jhoan Montero      ${NC}"
echo -e "${BLUE}         Farmacias Galeno-Apotheca             ${NC}"
echo -e "${BLUE}===============================================${NC}"

# 1. DEPENDENCIAS
echo -e "\n${YELLOW}[1/5] Instalando dependencias de Python y USB...${NC}"
sudo apt update
sudo apt install -y python3-pip python3-pil libusb-1.0-0-dev
pip3 install flask flask-cors python-escpos Pillow python-dotenv --break-system-packages

# 2. DETECCIÓN INTERACTIVA DE IMPRESORA
echo -e "\n${YELLOW}[2/5] Buscando impresora USB...${NC}"
echo "Dispositivos USB conectados actualmente:"
echo "------------------------------------------------"
lsusb
echo "------------------------------------------------"
echo -e "${YELLOW}Busca el ID que corresponda a tu impresora (ej: 1fc9:2016)${NC}"

read -p "Ingresa el VendorID (los 4 caracteres antes de los :): " V_ID
read -p "Ingresa el ProductID (los 4 caracteres después de los :): " P_ID

# 3. CREACIÓN DEL .ENV
echo -e "\n${YELLOW}[3/5] Guardando configuración en .env...${NC}"
cat <<EOF > .env
PRINTER_VENDOR_ID=0x$V_ID
PRINTER_PRODUCT_ID=0x$P_ID
EOF
echo -e "${GREEN}✔ Configuración guardada en .env${NC}"

# 4. REGLA UDEV DINÁMICA
echo -e "\n${YELLOW}[4/5] Configurando permisos USB (Regla UDEV)...${NC}"
# Usamos las variables que ingresaste para crear la regla
echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$V_ID\", ATTR{idProduct}==\"$P_ID\", MODE=\"0666\", GROUP=\"plugdev\"" | sudo tee /etc/udev/rules.d/99-printer.rules

sudo udevadm control --reload-rules
sudo udevadm trigger
echo -e "${GREEN}✔ Regla USB aplicada para $V_ID:$P_ID${NC}"

# 5. CONFIGURACIÓN DEL SERVICIO
echo -e "\n${YELLOW}[5/5] Configurando inicio automático...${NC}"
USER_NAME=$(whoami)
CURRENT_DIR=$(pwd)

sudo tee /etc/systemd/system/pos_proxy.service > /dev/null <<EOF
[Unit]
Description=POS Proxy Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $CURRENT_DIR/impresora_proxy.py
WorkingDirectory=$CURRENT_DIR
EnvironmentFile=$CURRENT_DIR/.env
StandardOutput=inherit
StandardError=inherit
Restart=always
User=$USER_NAME

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pos_proxy.service
sudo systemctl restart pos_proxy.service

echo -e "\n${GREEN}===============================================${NC}"
echo -e "${GREEN}    ¡INSTALACIÓN COMPLETADA CON ÉXITO!    ${NC}"
echo -e "${BLUE}===============================================${NC}"