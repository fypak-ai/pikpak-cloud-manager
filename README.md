# PikPak Cloud Manager

Gerencie seus arquivos PikPak direto do navegador — extraia links de compartilhamentos, navegue na sua nuvem e envie para o Dropbox.

## ✅ Requisitos

- Windows 10 ou 11
- Python 3.10+ ([python.org](https://www.python.org/downloads/))

## 📦 Instalação (primeira vez)

Abra o **PowerShell** e rode os comandos abaixo um por um:

### 1. Criar pasta e baixar os arquivos

```powershell
mkdir C:\PikPakManager
cd C:\PikPakManager
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fypak-ai/pikpak-cloud-manager/main/pikpak_extractor.py" -OutFile "pikpak_extractor.py"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fypak-ai/pikpak-cloud-manager/main/v7_template.html" -OutFile "v7_template.html"
```

### 2. Instalar dependências

```powershell
pip install flask requests
```

### 3. Iniciar o app

```powershell
python pikpak_extractor.py
```

Acesse no navegador: **http://localhost:5000**

---

## 🔄 Atualizar (versões futuras)

```powershell
cd C:\PikPakManager
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fypak-ai/pikpak-cloud-manager/main/pikpak_extractor.py" -OutFile "pikpak_extractor.py"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fypak-ai/pikpak-cloud-manager/main/v7_template.html" -OutFile "v7_template.html"
python pikpak_extractor.py
```

---

## 🚀 Funcionalidades

- **Link Compartilhado** — cole uma URL `mypikpak.com/s/...` e extraia todos os links de download
- **Minha Nuvem** — navegue pelos seus arquivos PikPak com login via Access Token
- **Envio para Dropbox** — selecione arquivos e envie em massa para o Dropbox
- **Visualizador de texto** — abre automaticamente arquivos `.txt` com conteúdo magnet/links

---

## 🔑 Login

O app usa **Access Token** do PikPak (mais confiável que email/senha):

1. Abra o PikPak Web ou App
2. Pressione **F12** → aba **Network**
3. Filtre por `api/v1` e copie o header `Authorization: Bearer XXX`
4. Cole o token no campo correspondente no app

---

## 📁 Estrutura

```
C:\PikPakManager\
├── pikpak_extractor.py   # Backend Flask
├── v7_template.html      # Interface web
└── pikpak_tokens.json    # Tokens salvos (gerado automaticamente)
```
