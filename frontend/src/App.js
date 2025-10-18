import React, { useState, useEffect, useCallback, useRef } from 'react';
import { auth, game } from './api';
import Sidebar from './components/Sidebar';
import CraftingArea from './components/CraftingArea';
import CraftingQueue from './components/CraftingQueue';
import Canvas from './components/Canvas';
import { gameInfoContent } from './GameInfo';
import './App.css';

const ERAS = [
  'Hunter-Gatherer', 'Agriculture', 'Metallurgy', 'Steam & Industry',
  'Electric Age', 'Computing', 'Futurism', 'Interstellar', 'Arcana', 'Beyond'
];

const COLOR_THEMES = {
  light: { name: 'Light', primary: '#e67e22', secondary: '#3498db' },
  dark: { name: 'Dark', primary: '#e94560', secondary: '#00d4ff' },
  blue: { name: 'Ocean', primary: '#1976d2', secondary: '#42a5f5' },
  pink: { name: 'Pink', primary: '#e91e63', secondary: '#ff6b9d' },
  green: { name: 'Forest', primary: '#27ae60', secondary: '#4caf50' },
  purple: { name: 'Twilight', primary: '#8e44ad', secondary: '#ab47bc' },
  red: { name: 'Fire', primary: '#c0392b', secondary: '#e74c3c' },
  gray: { name: 'Steel', primary: '#7f8c8d', secondary: '#95a5a6' },
};

function App() {
  const [user, setUser] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [authMode, setAuthMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [craftingOperations, setCraftingOperations] = useState([]); // Array of crafting ops
  const [notification, setNotification] = useState(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [selectedObject, setSelectedObject] = useState(null);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showEraUnlockModal, setShowEraUnlockModal] = useState(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [upgradeKey, setUpgradeKey] = useState('');
  const [upgradeError, setUpgradeError] = useState('');
  
  const longPressTimer = useRef(null);
  const [isLongPress, setIsLongPress] = useState(false);

  useEffect(() => {
    document.body.className = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  const handleThemeClick = () => {
    if (!isLongPress) {
      setTheme(prev => prev === 'light' ? 'dark' : 'light');
    }
  };
  
  const handleThemeMouseDown = () => {
    setIsLongPress(false);
    longPressTimer.current = setTimeout(() => {
      setIsLongPress(true);
      setShowColorPicker(true);
    }, 500);
  };
  
  const handleThemeMouseUp = () => {
    clearTimeout(longPressTimer.current);
    setTimeout(() => setIsLongPress(false), 100);
  };
  
  const handleColorSelect = (colorKey) => {
    setTheme(colorKey);
    setShowColorPicker(false);
  };

  const showNotification = useCallback((message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
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
    
    // Auto-refresh game state every second
    const interval = setInterval(loadGameState, 1000);
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
      showNotification('🎮 Welcome to TycoonCraft!', 'success');
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
    // Create a unique ID for this crafting operation
    const craftId = Date.now() + Math.random();
    
    // Add to crafting operations
    setCraftingOperations(prev => [...prev, {
      id: craftId,
      objectA,
      objectB,
      status: 'crafting'
    }]);
    
    try {
      const response = await game.craft(objectA.id, objectB.id);
      
      // Update the operation status
      setCraftingOperations(prev => 
        prev.map(op => op.id === craftId ? { ...op, status: 'success', result: response.data } : op)
      );
      
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
      
      // Remove the operation after 2 seconds
      setTimeout(() => {
        setCraftingOperations(prev => prev.filter(op => op.id !== craftId));
      }, 2000);
      
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Crafting failed';
      
      // Update operation to failed
      setCraftingOperations(prev => 
        prev.map(op => op.id === craftId ? { ...op, status: 'failed', error: errorMsg } : op)
      );
      
      setError(errorMsg);
      showNotification(errorMsg, 'error');
      
      // Remove failed operation after 3 seconds
      setTimeout(() => {
        setCraftingOperations(prev => prev.filter(op => op.id !== craftId));
      }, 3000);
    }
  };

  const handlePlace = async (objectId, x, y) => {
    try {
      const response = await game.place(objectId, x, y);
      await loadGameState();
      
      // Check if a new era was unlocked!
      if (response.data.era_unlocked) {
        setShowEraUnlockModal({
          era: response.data.era_unlocked,
          message: response.data.message
        });
        showNotification(`🎉 ${response.data.message}`, 'success');
      } else {
        showNotification('✅ Object placed!', 'success');
      }
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
      showNotification('🗑️ Object removed!', 'info');
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
      showNotification('💾 Game exported!', 'success');
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
      showNotification('📂 Game imported!', 'success');
    } catch (err) {
      showNotification('Import failed', 'error');
    }
  };

  const handleUpgradeSubmit = async (e) => {
    e.preventDefault();
    setUpgradeError('');
    
    try {
      const response = await game.redeemUpgradeKey(upgradeKey);
      showNotification(response.data.message, 'success');
      setShowUpgradeModal(false);
      setUpgradeKey('');
      await loadGameState();
    } catch (err) {
      setUpgradeError(err.response?.data?.error || 'Failed to redeem key');
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
          <h1>🏛️ TycoonCraft</h1>
          <p className="tagline">Build Your Civilization Through Crafting</p>
          
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
    <div className={`app ${theme}`}>
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          {notification.message}
        </div>
      )}
      
      <div className="header">
        <div className="header-left">
          <h1>🏛️ TycoonCraft</h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <span className="era-badge">{gameState.profile.current_era}</span>
            <span className="era-progress">
              Era {gameState.era_unlocks.length} of {ERAS.length}
            </span>
          </div>
        </div>
        <div className="header-center">
          <div className="resource">
            <span className="resource-icon">💰</span>
            <span className="resource-value">{Math.floor(gameState.profile.coins)}</span>
            <span className="resource-label">Coins</span>
          </div>
          <div className="resource">
            <span className="resource-icon">💎</span>
            <span className="resource-value">{Math.floor(gameState.profile.time_crystals)}</span>
            <span className="resource-label">Crystals</span>
          </div>
        </div>
        <div className="header-right">
          {!gameState?.profile?.is_pro && (
            <button 
              onClick={() => setShowUpgradeModal(true)} 
              className="btn-upgrade"
              title="Upgrade to Pro"
            >
              ⭐ Upgrade
            </button>
          )}
          <button 
            onClick={handleThemeClick}
            onMouseDown={handleThemeMouseDown}
            onMouseUp={handleThemeMouseUp}
            onMouseLeave={handleThemeMouseUp}
            onTouchStart={handleThemeMouseDown}
            onTouchEnd={handleThemeMouseUp}
            className="btn-icon" 
            title="Click to toggle, long-press for colors"
          >
            {theme === 'light' ? '🌙' : theme === 'dark' ? '☀️' : '🎨'}
          </button>
          <button onClick={handleExport} className="btn-small">💾 Export</button>
          <label className="btn-small">
            📂 Import
            <input type="file" accept=".json" onChange={handleImport} style={{display: 'none'}} />
          </label>
          <button onClick={handleLogout} className="btn-small">🚪 Logout</button>
          <button onClick={() => setShowInfoModal(true)} className="btn-icon" title="Game Info">
            ℹ️
          </button>
        </div>
      </div>

      <div className="game-container">
        <Sidebar 
          discoveries={gameState.discoveries}
          allObjects={gameState.all_objects}
          eraUnlocks={gameState.era_unlocks}
          currentEra={gameState.profile.current_era}
          eras={ERAS}
          onObjectInfo={setSelectedObject}
        />
        
        <div className="main-area">
          <div className="top-section-container">
            {/* Object Info Panel */}
            <div className="object-info-panel">
              <h3>📋 Object Details</h3>
              {selectedObject ? (
                <div className="object-info-content">
                  {selectedObject.image_path && (
                    <div className="object-info-image-container">
                      <img 
                        src={selectedObject.image_path} 
                        alt={selectedObject.object_name}
                        className="object-info-image"
                      />
                    </div>
                  )}
                  
                  <div className="object-info-details">
                    <div className="object-info-name">{selectedObject.object_name}</div>
                    <div className="object-info-flavor">{selectedObject.flavor_text}</div>
                    
                    <div className="object-info-stats">
                      <div className="object-info-stat">
                        <span className="object-info-stat-label">💰 Cost</span>
                        <span className="object-info-stat-value">{selectedObject.cost}</span>
                      </div>
                      <div className="object-info-stat">
                        <span className="object-info-stat-label">📊 Income/sec</span>
                        <span className="object-info-stat-value">{selectedObject.income_per_second}</span>
                      </div>
                      {parseFloat(selectedObject.time_crystal_generation) > 0 && (
                        <div className="object-info-stat">
                          <span className="object-info-stat-label">💎 Crystals/sec</span>
                          <span className="object-info-stat-value">{selectedObject.time_crystal_generation}</span>
                        </div>
                      )}
                      <div className="object-info-stat">
                        <span className="object-info-stat-label">📐 Size</span>
                        <span className="object-info-stat-value">{selectedObject.footprint_w}×{selectedObject.footprint_h}</span>
                      </div>
                      {selectedObject.build_time && parseFloat(selectedObject.build_time) > 0 && (
                        <div className="object-info-stat">
                          <span className="object-info-stat-label">🔨 Build Time</span>
                          <span className="object-info-stat-value">{selectedObject.build_time}s</span>
                        </div>
                      )}
                      {selectedObject.operation_duration && parseFloat(selectedObject.operation_duration) > 0 && (
                        <div className="object-info-stat">
                          <span className="object-info-stat-label">⏱️ Duration</span>
                          <span className="object-info-stat-value">{selectedObject.operation_duration}s</span>
                        </div>
                      )}
                      <div className="object-info-stat">
                        <span className="object-info-stat-label">🏛️ Era</span>
                        <span className="object-info-stat-value">{selectedObject.era_name}</span>
                      </div>
                      <div className="object-info-stat">
                        <span className="object-info-stat-label">📁 Category</span>
                        <span className="object-info-stat-value">{selectedObject.category}</span>
                      </div>
                    </div>
                    
                    {selectedObject.is_keystone && (() => {
                      const nextEra = ERAS[ERAS.indexOf(selectedObject.era_name) + 1];
                      return (
                        <div className="object-info-keystone">
                          🔑 Keystone Object - Place to unlock <strong>{nextEra || 'next era'}</strong>!
                        </div>
                      );
                    })()}
                  </div>
                </div>
              ) : (
                <div className="object-info-empty">
                  Click the ℹ️ icon on any object in the sidebar to view its details here
                </div>
              )}
            </div>
            
            {/* Crafting and Queue */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <CraftingArea 
                  discoveries={gameState.discoveries}
                  onCraft={handleCraft}
                  playerCoins={gameState.profile.coins}
                />
                
                {craftingOperations.length > 0 && (
                  <CraftingQueue 
                    craftingOperations={craftingOperations}
                  />
                )}
              </div>
            </div>
          </div>
          
          <Canvas 
            placedObjects={gameState.placed_objects}
            discoveries={gameState.discoveries}
            onPlace={handlePlace}
            onRemove={handleRemove}
            currentEra={gameState.profile.current_era}
          />
        </div>
      </div>

      {/* Color Picker Modal */}
      {showColorPicker && (
        <div className="modal-overlay" onClick={() => setShowColorPicker(false)}>
          <div className="color-picker-modal" onClick={(e) => e.stopPropagation()}>
            <h3>🎨 Choose Your Theme</h3>
            <div className="color-presets">
              {Object.entries(COLOR_THEMES).map(([key, theme]) => (
                <div
                  key={key}
                  className={`color-preset ${key === theme ? 'active' : ''}`}
                  style={{
                    background: `linear-gradient(135deg, ${theme.primary} 0%, ${theme.secondary} 100%)`
                  }}
                  onClick={() => handleColorSelect(key)}
                >
                  {theme.name}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Game Info Modal */}
      {showInfoModal && (
        <div className="modal-overlay" onClick={() => setShowInfoModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px' }}>
            <button className="modal-close" onClick={() => setShowInfoModal(false)}>✕</button>
            <div 
              className="info-modal-content"
              dangerouslySetInnerHTML={{ __html: gameInfoContent }}
            />
          </div>
        </div>
      )}

      {/* Upgrade Modal */}
      {showUpgradeModal && (
        <div className="modal-overlay" onClick={() => setShowUpgradeModal(false)}>
          <div className="modal upgrade-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowUpgradeModal(false)}>✕</button>
            <h2>⭐ Upgrade to Pro</h2>
            <p className="upgrade-description">
              Unlock Pro status to get <strong>500 daily API calls</strong> instead of 20!
            </p>
            <form onSubmit={handleUpgradeSubmit}>
              <input
                type="text"
                placeholder="Enter your upgrade key"
                value={upgradeKey}
                onChange={(e) => setUpgradeKey(e.target.value)}
                className="upgrade-input"
                required
              />
              {upgradeError && <div className="upgrade-error">{upgradeError}</div>}
              <button type="submit" className="upgrade-submit-button">
                Redeem Key
              </button>
            </form>
            <div className="upgrade-info">
              <h3>Pro Benefits:</h3>
              <ul>
                <li>✅ 500 daily API calls (vs 20 standard)</li>
                <li>✅ More crafting opportunities per day</li>
                <li>✅ Faster progression through eras</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Era Unlock Celebration Modal */}
      {showEraUnlockModal && (
        <div className="modal-overlay era-unlock-overlay">
          <div className="era-unlock-modal">
            <div className="era-unlock-animation">
              <div className="era-unlock-icon">🎉</div>
              <div className="era-unlock-sparkles">
                <span>✨</span>
                <span>💫</span>
                <span>⭐</span>
                <span>🌟</span>
                <span>✨</span>
                <span>💫</span>
              </div>
            </div>
            <h2 className="era-unlock-title">New Era Unlocked!</h2>
            <div className="era-unlock-era">{showEraUnlockModal.era}</div>
            <p className="era-unlock-message">{showEraUnlockModal.message}</p>
            <div className="era-unlock-description">
              You can now craft and place objects from the <strong>{showEraUnlockModal.era}</strong> era!
            </div>
            <button 
              className="era-unlock-button"
              onClick={() => setShowEraUnlockModal(null)}
            >
              ⚡ Continue Your Journey!
            </button>
          </div>
        </div>
      )}

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
