#!/bin/bash

echo "🎮 TycoonCraft Quick Setup Script 🎮"
echo "====================================="
echo ""

# Check if .env exists
if [ ! -f backend/.env ]; then
    echo "📝 Creating .env file..."
    cat > backend/.env << EOF
DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=True
DB_NAME=tycooncraft
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=your_openai_api_key_here
EOF
    echo "⚠️  Please edit backend/.env and add your OpenAI API key!"
    echo ""
fi

# Setup backend
echo "🐍 Setting up backend..."
cd backend
python3 -m venv venv 2>/dev/null || python -m venv venv
source venv/bin/activate || . venv/Scripts/activate
pip install -r requirements.txt --quiet

echo "🗄️  Running migrations..."
python manage.py makemigrations
python manage.py migrate

echo "🎲 Initializing starter objects..."
python manage.py initialize_starter_objects

echo "👤 Creating admin user (username: admin, password: admin)..."
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@tycooncraft.com', 'admin')" 2>/dev/null

cd ..

# Setup frontend
echo "⚛️  Setting up frontend..."
cd frontend
npm install --silent

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  Backend:  cd backend && source venv/bin/activate && python manage.py runserver"
echo "  Frontend: cd frontend && npm start"
echo ""
echo "Access the application at http://localhost:3000"
echo "Admin panel at http://localhost:8000/admin (username: admin, password: admin)"
echo ""
echo "⚠️  Don't forget to add your OpenAI API key to backend/.env!"
