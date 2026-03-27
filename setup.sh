#!/bin/bash
set -e

echo "🚀 Setting up contentflowz with Flox + Doppler..."
echo ""

# Check if Flox is installed
if ! command -v flox &> /dev/null; then
    echo "❌ Flox is not installed!"
    echo "   Install it from: https://flox.dev"
    exit 1
fi

echo "✅ Flox detected"

# Check if Doppler is installed
if ! command -v doppler &> /dev/null; then
    echo "⚠️  Doppler not found! Installing..."
    # Install Doppler CLI
    (curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh || wget -t 3 -qO- https://cli.doppler.com/install.sh) | sh
    echo "✅ Doppler installed"
else
    echo "✅ Doppler detected (v$(doppler --version | cut -d' ' -f2))"
fi

# Check if Flox environment is initialized
if [ ! -d ".flox" ]; then
    echo "📦 Initializing Flox environment..."
    flox init
    flox install python311
else
    echo "✅ Flox environment already initialized"
fi

# Create Python virtual environment inside Flox
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    flox activate -- python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "📥 Installing Python dependencies..."
    flox activate -- ./venv/bin/pip install --upgrade pip -q
    flox activate -- ./venv/bin/pip install -r requirements.txt -q
    echo "✅ Dependencies installed"
else
    echo "⚠️  No requirements.txt found"
fi

# Create project structure
echo "📁 Creating project structure..."
mkdir -p src/{seo/{agents,tools,workflows,config},newsletter/{agents,schemas,tools,templates,config},articles/{agents,schemas,tools,templates,config}}
mkdir -p tests scripts monitoring docs

echo ""
echo "🔐 Configuration Doppler"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if Doppler is already configured for this project
if doppler configure get project.name >/dev/null 2>&1; then
    DOPPLER_PROJECT=$(doppler configure get project.name 2>/dev/null)
    DOPPLER_CONFIG=$(doppler configure get config.name 2>/dev/null)
    echo "✅ Doppler déjà configuré:"
    echo "   Project: $DOPPLER_PROJECT"
    echo "   Config: $DOPPLER_CONFIG"
    echo ""
    read -p "Voulez-vous reconfigurer Doppler? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Configuration Doppler conservée"
        # Create fallback .env for local dev without doppler run
        echo "📝 Création du fichier .env local (fallback)..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
        fi
        echo ""
        echo "✅ Setup complete!"
        echo ""
        echo "🚀 Pour démarrer avec Doppler:"
        echo "   doppler run -- flox activate"
        echo "   OU dans l'environnement:"
        echo "   flox activate"
        echo "   doppler run -- python main.py"
        exit 0
    fi
fi

echo ""
echo "Configuration de Doppler pour contentflowz..."
echo ""

# Ask for project setup method
echo "Choisissez une option:"
echo "  1) Créer un nouveau projet Doppler 'contentflowz'"
echo "  2) Utiliser un projet Doppler existant"
echo "  3) Utiliser .env local (sans Doppler)"
echo ""
read -p "Votre choix (1/2/3): " -n 1 -r choice
echo ""
echo ""

case $choice in
    1)
        # Create new Doppler project
        echo "📦 Création du projet Doppler 'contentflowz'..."
        if doppler projects create contentflowz --description "AI Robots automation system" 2>/dev/null; then
            echo "✅ Projet créé"
        else
            echo "ℹ️  Projet 'contentflowz' existe déjà ou erreur"
        fi
        
        # Configure project
        doppler setup --project contentflowz --config dev --no-interactive
        
        echo ""
        echo "📝 Ajout des secrets au projet Doppler..."
        echo "   Vous pouvez les ajouter maintenant ou plus tard via:"
        echo "   • Dashboard: https://dashboard.doppler.com"
        echo "   • CLI: doppler secrets set KEY=value"
        echo ""
        echo "Secrets nécessaires:"
        echo "  - OPENAI_API_KEY or ANTHROPIC_API_KEY or GROQ_API_KEY (LLM)"
        echo "  - YDC_API_KEY or SERPER_API_KEY (STORM research)"
        echo "  - EXA_API_KEY (newsletter)"
        echo "  - FIRECRAWL_API_KEY (articles scraping)"
        echo "  - SENDGRID_API_KEY (email)"
        echo "  - EMAIL_FROM (email address)"
        echo ""
        read -p "Voulez-vous les ajouter maintenant interactivement? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            source_interactive_doppler_setup
        fi
        ;;
    2)
        # Use existing project
        echo "Projets Doppler disponibles:"
        doppler projects
        echo ""
        read -p "Nom du projet: " project_name
        read -p "Nom de la config (dev/staging/prod): " config_name
        
        doppler setup --project "$project_name" --config "$config_name" --no-interactive
        echo "✅ Doppler configuré avec $project_name ($config_name)"
        ;;
    3)
        # Use local .env
        echo "📝 Configuration avec .env local (sans Doppler)..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
        fi
        source_interactive_env_setup
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup terminé!"
echo ""
if [ "$choice" != "3" ]; then
    echo "📝 Pour utiliser Doppler:"
    echo "1. Lancer avec Doppler: doppler run -- flox activate"
    echo "2. Ou dans l'environnement: flox activate && doppler run -- python main.py"
    echo "3. Dashboard: https://dashboard.doppler.com"
else
    echo "📝 Prochaines étapes:"
    echo "1. Éditer .env: nano .env"
    echo "2. Activer: flox activate"
    echo "3. Lancer: python main.py"
fi
echo ""
echo "💡 L'environnement Flox est reproductible!"
echo "   Partagez .flox/env/manifest.toml avec votre équipe."
echo ""

# Function for interactive Doppler secret setup
source_interactive_doppler_setup() {
    echo ""
    echo "Configuration interactive des secrets Doppler..."
    echo "Appuyez sur ENTER pour ignorer un secret."
    echo ""
    
    # LLM Providers (user chooses one)
    echo "🤖 LLM Provider (choose one):"
    read -p "GROQ_API_KEY (FREE, recommended): " val && [ -n "$val" ] && doppler secrets set GROQ_API_KEY="$val"
    read -p "OPENAI_API_KEY (premium): " val && [ -n "$val" ] && doppler secrets set OPENAI_API_KEY="$val"
    read -p "ANTHROPIC_API_KEY (premium): " val && [ -n "$val" ] && doppler secrets set ANTHROPIC_API_KEY="$val"
    
    # STORM Research (user chooses one)
    echo ""
    echo "🔍 STORM Research Provider (choose one):"
    read -p "YDC_API_KEY (You.com, recommended): " val && [ -n "$val" ] && doppler secrets set YDC_API_KEY="$val"
    read -p "SERPER_API_KEY (alternative): " val && [ -n "$val" ] && doppler secrets set SERPER_API_KEY="$val"
    
    # Other APIs
    echo ""
    echo "📦 Other APIs:"
    read -p "EXA_API_KEY (newsletter): " val && [ -n "$val" ] && doppler secrets set EXA_API_KEY="$val"
    read -p "FIRECRAWL_API_KEY (scraping): " val && [ -n "$val" ] && doppler secrets set FIRECRAWL_API_KEY="$val"
    read -p "SENDGRID_API_KEY (email): " val && [ -n "$val" ] && doppler secrets set SENDGRID_API_KEY="$val"
    read -p "EMAIL_FROM (email address): " val && [ -n "$val" ] && doppler secrets set EMAIL_FROM="$val"
    
    echo ""
    echo "✅ Secrets configurés dans Doppler!"
}

# Function for interactive .env setup (fallback)
source_interactive_env_setup() {
    echo ""
    echo "Vous pouvez appuyer sur ENTER pour laisser vide."
    echo ""
    
    prompt_api_key() {
        local key_name=$1
        local key_description=$2
        echo "📌 ${key_description}"
        read -p "   ${key_name}: " value
        if [ -n "$value" ]; then
            if grep -q "^${key_name}=" .env 2>/dev/null; then
                sed -i "s|^${key_name}=.*|${key_name}=${value}|" .env
            else
                echo "${key_name}=${value}" >> .env
            fi
        fi
    }
    
    # LLM Providers
    echo "🤖 LLM Provider (choose one):"
    prompt_api_key "GROQ_API_KEY" "Groq API Key (FREE, recommended)"
    prompt_api_key "OPENAI_API_KEY" "OpenAI API Key"
    prompt_api_key "ANTHROPIC_API_KEY" "Anthropic API Key"
    
    # STORM Research
    echo ""
    echo "🔍 STORM Research (choose one):"
    prompt_api_key "YDC_API_KEY" "You.com API Key (recommended)"
    prompt_api_key "SERPER_API_KEY" "Serper API Key"
    
    # Other APIs
    echo ""
    echo "📦 Other APIs:"
    prompt_api_key "EXA_API_KEY" "Exa AI API Key"
    prompt_api_key "FIRECRAWL_API_KEY" "Firecrawl API Key"
    prompt_api_key "SENDGRID_API_KEY" "SendGrid API Key"
    prompt_api_key "EMAIL_FROM" "Email From"
    
    echo ""
    echo "✅ Configuration .env sauvegardée!"
}
