import React, { useState, useEffect, useCallback } from 'react';
import { auth, game } from './api';
import Sidebar from './components/Sidebar';
import CraftingArea from './components/CraftingArea';
import Canvas from './components/Canvas';
import './App.css';

const ERAS = [
  'Hunter-Gatherer', 'Agriculture', 'Metallurgy', 'Steam & Industry',
  'Electric Age', 'Computing', 'Futurism', 'Interstellar', 'Arcana', 'Beyond'
];

function App() {
  const [user, setUser] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [authMode, setAuthMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [crafting, setCrafting] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = useCallback((message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  }, []);

  const loadGameState = useCallback(async () => {
    try {
      const response = await game.getState();
      setGameState(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to load game state:', err);
      if (err.response?.status === 401) {
        setUser(null);
      }
    }
  }, []);

  useEffect(() => {
    loadGameState().finally(() => setLoading(false));
    
    // Auto-refresh game state every 5 seconds
    const interval = setInterval(loadGameState, 5000);
    return () => clearInterval(interval);
  }, [loadGameState]);

  const handleAuth = async (e) => {
    e.preventDefault();
    setError(null);
    
    try {
      let response;
      if (authMode === 'login') {
        response = await auth.login(username, password);
      } else {
        response = await auth.register(username, password, email);
      }
      
      setUser(response.data.user);
      await loadGameState();
      showNotification('Welcome to TycoonCraft!', 'success');
    } catch (err) {
      setError(err.response?.data?.error || 'Authentication failed');
    }
  };

  const handleLogout = async () => {
    try {
      await auth.logout();
      setUser(null);
      setGameState(null);
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  const handleCraft = async (objectA, objectB) => {
    if (crafting) return;
    
    setCrafting(true);
    setError(null);
    
    try {
      const response = await game.craft(objectA.id, objectB.id);
      
      if (response.data.newly_created) {
        showNotification(
          `🎉 New discovery! You created ${response.data.object.object_name}!`,
          'success'
        );
      } else if (response.data.newly_discovered) {
        showNotification(
          `✨ You discovered ${response.data.object.object_name}!`,
          'success'
        );
      } else {
        showNotification(
          `You already discovered ${response.data.object.object_name}`,
          'info'
        );
      }
      
      await loadGameState();
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Crafting failed';
      setError(errorMsg);
      showNotification(errorMsg, 'error');
    } finally {
      setCrafting(false);
    }
  };

  const handlePlace = async (objectId, x, y) => {
    try {
      await game.place(objectId, x, y);
      await loadGameState();
      showNotification('Object placed!', 'success');
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Placement failed';
      setError(errorMsg);
      showNotification(errorMsg, 'error');
    }
  };

  const handleRemove = async (placedId) => {
    try {
      await game.remove(placedId);
      await loadGameState();
      showNotification('Object removed!', 'info');
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Removal failed';
      setError(errorMsg);
      showNotification(errorMsg, 'error');
    }
  };

  const handleExport = async () => {
    try {
      const response = await game.export();
      const dataStr = JSON.stringify(response.data, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `tycooncraft-save-${Date.now()}.json`;
      link.click();
      showNotification('Game exported!', 'success');
    } catch (err) {
      showNotification('Export failed', 'error');
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      await game.import(data);
      await loadGameState();
      showNotification('Game imported!', 'success');
    } catch (err) {
      showNotification('Import failed', 'error');
    }
  };

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loader"></div>
        <p>Loading TycoonCraft...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="auth-screen">
        <div className="auth-container">
          <h1>TycoonCraft</h1>
          <p className="tagline">Craft Your Civilization</p>
          
          <form onSubmit={handleAuth}>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {authMode === 'register' && (
              <input
                type="email"
                placeholder="Email (optional)"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            )}
            
            {error && <div className="error">{error}</div>}
            
            <button type="submit">
              {authMode === 'login' ? 'Login' : 'Register'}
            </button>
          </form>
          
          <button 
            className="toggle-auth"
            onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
          >
            {authMode === 'login' ? 'Need an account? Register' : 'Have an account? Login'}
          </button>
        </div>
      </div>
    );
  }

  if (!gameState) {
    return <div className="loading-screen"><div className="loader"></div></div>;
  }

  return (
    <div className="app">
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          {notification.message}
        </div>
      )}
      
      <div className="header">
        <div className="header-left">
          <h1>TycoonCraft</h1>
          <span className="era-badge">{gameState.profile.current_era}</span>
        </div>
        <div className="header-center">
          <div className="resource">
            <span className="resource-icon">💰</span>
            <span className="resource-value">{Math.floor(gameState.profile.coins)}</span>
          </div>
          <div className="resource">
            <span className="resource-icon">💎</span>
            <span className="resource-value">{Math.floor(gameState.profile.time_crystals)}</span>
          </div>
        </div>
        <div className="header-right">
          <button onClick={handleExport} className="btn-small">Export</button>
          <label className="btn-small">
            Import
            <input type="file" accept=".json" onChange={handleImport} style={{display: 'none'}} />
          </label>
          <button onClick={handleLogout} className="btn-small">Logout</button>
        </div>
      </div>

      <div className="game-container">
        <Sidebar 
          discoveries={gameState.discoveries}
          allObjects={gameState.all_objects}
          eraUnlocks={gameState.era_unlocks}
          currentEra={gameState.profile.current_era}
          eras={ERAS}
        />
        
        <div className="main-area">
          <CraftingArea 
            discoveries={gameState.discoveries}
            onCraft={handleCraft}
            crafting={crafting}
          />
          
          <Canvas 
            placedObjects={gameState.placed_objects}
            discoveries={gameState.discoveries}
            onPlace={handlePlace}
            onRemove={handleRemove}
          />
        </div>
      </div>

      {error && (
        <div className="error-toast">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}
    </div>
  );
}

export default App;
