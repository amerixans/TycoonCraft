# TycoonCraft

A civilization-crafting tycoon game where players combine objects to discover new items, progressing through eras from Hunter-Gatherer to Beyond.

## Game Overview

TycoonCraft is a web-based incremental/tycoon game where players:
1. Start with 4 basic objects (Rock, Stick, Water, Dirt)
2. Combine any two objects to discover new ones
3. Purchase discovered objects with coins to place on a canvas
4. Generate income from placed objects
5. Progress through 10 eras by discovering keystone objects
6. Use AI-generated definitions and images for each crafted object

## Tech Stack

- **Backend**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL
- **Frontend**: React 18
- **AI**: OpenAI GPT-5-mini (crafting) + GPT-image-1-mini (images)
- **Deployment**: Nginx + Gunicorn on Ubuntu

## File Structure

```
tycooncraft/
├── backend/
│   ├── manage.py                    # Django management script
│   ├── requirements.txt             # Python dependencies
│   ├── tycooncraft/                 # Django project settings
│   │   ├── __init__.py
│   │   ├── settings.py              # Main configuration
│   │   ├── urls.py                  # URL routing
│   │   ├── wsgi.py                  # WSGI entry point
│   │   └── asgi.py                  # ASGI entry point
│   ├── game/                        # Main game app
│   │   ├── __init__.py
│   │   ├── models.py                # Database models
│   │   ├── views.py                 # API endpoints & game logic
│   │   ├── serializers.py           # DRF serializers
│   │   ├── urls.py                  # Game URL routing
│   │   ├── admin.py                 # Django admin configuration
│   │   └── management/
│   │       └── commands/
│   │           └── initialize_starter_objects.py
│   ├── prompts/                     # AI prompts & schemas
│   │   ├── crafting_recipe.txt      # Object generation prompt
│   │   ├── image_prompt.txt         # Image generation prompt
│   │   ├── object_capsule.json      # Input object schema
│   │   └── object_schema.json       # Output object schema
│   └── static/                      # Static files (collected here)
├── frontend/
│   ├── package.json                 # NPM dependencies
│   ├── public/
│   │   └── index.html               # HTML template
│   └── src/
│       ├── index.js                 # React entry point
│       ├── App.js                   # Main app component
│       ├── App.css                  # Main app styles
│       ├── api.js                   # Backend API client
│       └── components/
│           ├── Sidebar.js           # Object discovery sidebar
│           ├── Sidebar.css
│           ├── CraftingArea.js      # Crafting interface
│           ├── CraftingArea.css
│           ├── Canvas.js            # Object placement canvas
│           └── Canvas.css
├── deployment.md                    # Deployment guide
└── README.md                        # This file
```

## Features

### Core Gameplay
- **Crafting System**: Drag-and-drop interface to combine two objects
- **AI Generation**: New objects created dynamically using OpenAI models
- **Economy**: Coin and time crystal generation from placed objects
- **Canvas**: 1000x1000 tile grid-based placement system
- **Era Progression**: 10 eras with unique mechanics and keystone objects

### Eras
1. **Hunter-Gatherer** (0 crystals) - Decay mechanic
2. **Agriculture** (10 crystals) - Growth mechanic
3. **Metallurgy** (50 crystals) - Extraction chains
4. **Steam & Industry** (250 crystals) - Throughput
5. **Electric Age** (1,200 crystals) - Power grid
6. **Computing** (6,000 crystals) - Automation
7. **Futurism** (30,000 crystals) - Synthesis
8. **Interstellar** (150,000 crystals) - Logistics lanes
9. **Arcana** (800,000 crystals) - Enchantment
10. **Beyond** (4,000,000 crystals) - Sim layers

### User Features
- Account system with login/register
- Save/load game state (export/import JSON)
- Real-time coin and crystal updates
- Hover tooltips for placed objects
- Rate limiting (4 discoveries per user per minute)

### Technical Features
- RESTful API architecture
- Session-based authentication
- PostgreSQL database with indexes
- Rate limiting on API calls
- Image caching for crafted objects
- Global modifiers system
- Era progression tracking

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- OpenAI API key

### Local Development

1. **Setup Database**
```bash
createdb tycooncraft
```

2. **Setup Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "DJANGO_SECRET_KEY=your-secret-key" > .env
echo "DEBUG=True" >> .env
echo "OPENAI_API_KEY=your-openai-key" >> .env

python manage.py migrate
python manage.py initialize_starter_objects
python manage.py createsuperuser
python manage.py runserver
```

3. **Setup Frontend**
```bash
cd frontend
npm install
npm start
```

4. **Access Application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Admin Panel: http://localhost:8000/admin

## API Endpoints

### Authentication
- `POST /api/register/` - Register new user
- `POST /api/login/` - Login user
- `POST /api/logout/` - Logout user

### Game
- `GET /api/game-state/` - Get complete game state
- `POST /api/craft/` - Craft two objects together
  ```json
  {"object_a_id": 1, "object_b_id": 2}
  ```
- `POST /api/place/` - Place object on canvas
  ```json
  {"object_id": 5, "x": 10, "y": 20}
  ```
- `POST /api/remove/` - Remove placed object
  ```json
  {"placed_id": 15}
  ```
- `POST /api/unlock-era/` - Unlock next era
  ```json
  {"era_name": "Agriculture"}
  ```
- `GET /api/export/` - Export game state
- `POST /api/import/` - Import game state

## Game Mechanics

### Crafting
- Combine any two discovered objects
- First-time combinations call OpenAI to generate definition
- Subsequent combinations use cached results
- Results are shared globally across all players

### Economy
- Starting coins: 100
- Objects generate coins per second when operational
- Some objects generate time crystals (rare)
- Purchase objects to place on canvas
- Remove objects for partial refund

### Canvas
- 1000x1000 tile grid
- Grid-based placement (not free-form)
- Objects have footprint (width × height)
- No object rotation
- Objects can be moved after placement

### Era Progression
- Each era has a keystone object
- Discover keystone by crafting specific combination
- Purchase keystone with time crystals to unlock era
- Access to all previous era items retained

## Rate Limits

- User discoveries: 4 per minute
- Global API calls: 50 per minute
- Build time varies by object
- Operation duration determines object lifetime

## Database Models

- **GameObject**: Object definitions and stats
- **CraftingRecipe**: Crafting combinations
- **PlayerProfile**: User game state
- **Discovery**: Objects discovered by each player
- **PlacedObject**: Objects on player's canvas
- **EraUnlock**: Eras unlocked by player
- **RateLimit**: Rate limiting tracking

## Development Notes

### Adding New Starter Objects
```bash
python manage.py shell
from game.models import GameObject
from decimal import Decimal

GameObject.objects.create(
    object_name="New Object",
    era_name="Hunter-Gatherer",
    category="natural",
    cost=Decimal("10"),
    # ... other fields
)
```

### Viewing Logs
```bash
# Django logs
tail -f /var/log/tycooncraft/error.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

### Database Queries
```bash
python manage.py dbshell
```

## Troubleshooting

### "Rate limit exceeded"
Wait 60 seconds or increase limits in settings.py

### "Space occupied"
Objects overlap - choose different placement coordinates

### "Insufficient coins"
Generate more income by placing more objects

### Images not loading
Check MEDIA_ROOT and MEDIA_URL in settings.py

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For issues, questions, or support:
- Check deployment.md for deployment help
- Review this README for game mechanics
- Check Django logs for backend issues
- Check browser console for frontend issues

## Credits

- Built with Django, React, and OpenAI
- Pixel art styling inspired by retro games
- Game design by TycoonCraft team

---

**Version**: 1.0.0
**Last Updated**: October 17, 2025
