# TycoonCraft - Quick Start Guide

Get TycoonCraft running in 5 minutes!

## Option 1: Automated Setup (Recommended)

### Prerequisites
- Python 3.8+
- Node.js 16+
- PostgreSQL installed and running

### Steps

1. **Create Database**
```bash
createdb tycooncraft
```

2. **Run Setup Script**
```bash
chmod +x setup.sh
./setup.sh
```

3. **Add OpenAI API Key**
Edit `backend/.env` and replace `your_openai_api_key_here` with your actual key.

4. **Start Backend** (Terminal 1)
```bash
cd backend
source venv/bin/activate
python manage.py runserver
```

5. **Start Frontend** (Terminal 2)
```bash
cd frontend
npm start
```

6. **Play!**
Open http://localhost:3000 in your browser

## Option 2: Manual Setup

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file with your settings
echo "OPENAI_API_KEY=your_key_here" > .env
echo "DJANGO_SECRET_KEY=change-me" >> .env
echo "DEBUG=True" >> .env

python manage.py migrate
python manage.py initialize_starter_objects
python manage.py createsuperuser
python manage.py runserver
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

## First Time Playing

1. **Register**: Create an account on the login screen
2. **Start Crafting**: You begin with Rock, Stick, Water, and Dirt
3. **Combine Objects**: Drag one object onto another in the crafting area
4. **Discover**: Watch as AI generates new objects!
5. **Place Objects**: Drag discovered objects to the canvas to generate income
6. **Progress**: Use time crystals to unlock new eras

## Default Login

If you ran the setup script, there's an admin account:
- Username: `admin`
- Password: `admin`

Change this immediately for production!

## Troubleshooting

### "Port already in use"
Kill the process using port 8000 or 3000:
```bash
# Kill backend
lsof -ti:8000 | xargs kill -9

# Kill frontend
lsof -ti:3000 | xargs kill -9
```

### "Database does not exist"
```bash
createdb tycooncraft
```

### "Module not found"
Make sure virtual environment is activated and dependencies are installed:
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend won't start
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## What's Next?

- Read the full [README.md](README.md) for detailed documentation
- Check [deployment.md](deployment.md) for production deployment
- Explore the Django admin at http://localhost:8000/admin

## Game Tips

1. **Experiment**: Try combining everything!
2. **Read Descriptions**: Hover over objects to see their stats
3. **Plan Placement**: Objects need space on the grid
4. **Watch Resources**: Keep an eye on coins and crystals
5. **Unlock Eras**: Find keystone objects to progress
6. **Be Patient**: AI generation takes a few seconds

## Support

If you encounter issues:
1. Check the console for error messages
2. Look at Django logs: `backend/*.log`
3. Verify PostgreSQL is running: `pg_isready`
4. Ensure ports 3000 and 8000 are free

Enjoy crafting your civilization! 🎮
