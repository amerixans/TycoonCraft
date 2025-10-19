import React, { useState, useEffect } from 'react';
import { formatNumber } from '../utils/formatNumber';
import { hasAura, describeAuraModifier } from '../utils/aura';
import './Sidebar.css';

function Sidebar({ discoveries, allObjects, eraUnlocks, currentEra, eras, onObjectInfo }) {
  const [selectedEra, setSelectedEra] = useState(currentEra);
  const [searchTerm, setSearchTerm] = useState('');
  const [hoveredLockedEra, setHoveredLockedEra] = useState(null);

  // Update selectedEra when currentEra changes
  useEffect(() => {
    setSelectedEra(currentEra);
  }, [currentEra]);

  // Extract discovered objects directly from discoveries
  const discoveredObjects = discoveries.map(d => d.game_object);
  const unlockedEras = new Set(eraUnlocks.map(u => u.era_name));

  const getNextEra = (era) => {
    const index = eras.indexOf(era);
    return index >= 0 && index < eras.length - 1 ? eras[index + 1] : null;
  };

  const objectsByEra = {};
  eras.forEach(era => {
    // Include only objects that match this era (keystones belong to their own era)
    objectsByEra[era] = discoveredObjects.filter(obj =>
      obj.era_name === era
    );
  });

  const getEraStatus = (era) => {
    if (unlockedEras.has(era)) return 'unlocked';
    if (eras.indexOf(era) <= eras.indexOf(currentEra)) return 'available';
    return 'locked';
  };

  // Get the keystone object needed to unlock a specific era
  const getKeystoneForEra = (targetEra) => {
    const eraIndex = eras.indexOf(targetEra);
    if (eraIndex <= 0) return null; // First era has no keystone

    // Keystone belongs to the previous era
    const previousEra = eras[eraIndex - 1];

    // Find the keystone object in the previous era that unlocks the target era
    return allObjects.find(obj =>
      obj.era_name === previousEra && obj.is_keystone
    );
  };

  // Filter objects based on search term
  const filteredObjects = searchTerm
    ? discoveredObjects.filter(obj =>
        obj.object_name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : objectsByEra[selectedEra] || [];
  
  const handleInfoClick = (obj, e) => {
    e.stopPropagation();
    e.preventDefault();
    onObjectInfo(obj);
  };
  
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h3>📦 Objects</h3>
        <input
          type="text"
          className="search-input"
          placeholder="🔍 Search objects..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>
      
      {!searchTerm && (
        <div className="era-tabs">
          {eras.map(era => {
            const status = getEraStatus(era);
            const keystone = status === 'locked' ? getKeystoneForEra(era) : null;
            const hintText = keystone
              ? `Craft ${keystone.object_name} to unlock this era`
              : status === 'locked'
              ? 'Unlock previous eras first'
              : '';

            return (
              <button
                key={era}
                className={`era-tab ${status} ${selectedEra === era ? 'active' : ''}`}
                onClick={() => setSelectedEra(era)}
                disabled={status === 'locked'}
                onMouseEnter={() => status === 'locked' && setHoveredLockedEra(era)}
                onMouseLeave={() => setHoveredLockedEra(null)}
                title={hintText}
              >
                {era.split(' ')[0]}
              </button>
            );
          })}
          {hoveredLockedEra && (() => {
            const keystone = getKeystoneForEra(hoveredLockedEra);
            return keystone ? (
              <div className="era-lock-hint">
                Craft <strong>{keystone.object_name}</strong> to unlock this era
              </div>
            ) : null;
          })()}
        </div>
      )}
      
      <div className="objects-list">
        {searchTerm && (
          <h4>🔍 Search Results ({filteredObjects.length})</h4>
        )}
        {!searchTerm && (
          <h4>{selectedEra}</h4>
        )}
        <div className="objects-grid">
          {filteredObjects.length === 0 ? (
            <div className="no-objects">
              {searchTerm ? '❌ No objects found' : '🔒 No objects discovered yet'}
            </div>
          ) : (
            filteredObjects.map(obj => {
              const auraActive = hasAura(obj);
              const auraTooltip = auraActive
                ? obj.global_modifiers
                    .map((modifier) => {
                      const details = describeAuraModifier(modifier);
                      const effectText =
                        details.effects.length > 0
                          ? details.effects.join(', ')
                          : 'No stat changes';
                      return `${details.categories}: ${effectText} (${details.activation}, ${details.maxStacks > 1 ? `stacks x${details.maxStacks}` : 'single-stack'})`;
                    })
                    .join('\n')
                : '';
              let hoverTitle = obj.is_keystone
                ? `🔑 Keystone: Place to unlock ${getNextEra(obj.era_name) || 'next era'}!`
                : 'Drag to craft or place';
              if (auraActive) {
                hoverTitle += `\n🌀 Aura active`;
              }
              return (
              <div 
                key={obj.id}
                className={`object-item ${obj.is_keystone ? 'keystone' : ''}`}
                title={hoverTitle}
                draggable={true}
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = 'copy';
                  e.dataTransfer.setData('objectId', obj.id.toString());
                  e.dataTransfer.setData('text/plain', obj.object_name);
                  
                  // Create custom drag image with just the object image
                  const dragImage = document.createElement('div');
                  dragImage.style.width = '64px';
                  dragImage.style.height = '64px';
                  dragImage.style.background = 'var(--bg-secondary)';
                  dragImage.style.border = '3px solid var(--accent-secondary)';
                  dragImage.style.borderRadius = '12px';
                  dragImage.style.display = 'flex';
                  dragImage.style.alignItems = 'center';
                  dragImage.style.justifyContent = 'center';
                  dragImage.style.position = 'absolute';
                  dragImage.style.top = '-1000px';
                  dragImage.style.overflow = 'hidden';
                  dragImage.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
                  
                  if (obj.image_path) {
                    const img = document.createElement('img');
                    img.src = obj.image_path;
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'contain';
                    img.style.imageRendering = 'pixelated';
                    dragImage.appendChild(img);
                  } else {
                    const placeholder = document.createElement('div');
                    placeholder.textContent = obj.object_name.substring(0, 2).toUpperCase();
                    placeholder.style.fontSize = '1.5rem';
                    placeholder.style.fontWeight = '900';
                    placeholder.style.color = 'var(--accent-primary)';
                    dragImage.appendChild(placeholder);
                  }
                  
                  document.body.appendChild(dragImage);
                  e.dataTransfer.setDragImage(dragImage, 32, 32);
                  
                  // Clean up after drag starts
                  setTimeout(() => {
                    document.body.removeChild(dragImage);
                  }, 0);
                }}
              >
                <div className="object-image-container">
                  {obj.image_path ? (
                    <img 
                      src={obj.image_path} 
                      alt={obj.object_name}
                      className="object-item-image"
                    />
                  ) : (
                    <div className="object-image-placeholder">
                      {obj.object_name.substring(0, 2).toUpperCase()}
                    </div>
                  )}
                </div>
                <div className="object-content">
                  <div className="object-name">
                    {obj.object_name}
                  </div>
                  <div className="object-stats">
                    <div>💰 {formatNumber(obj.cost)}</div>
                    <div>📊 {formatNumber(obj.income_per_second)}/s</div>
                  </div>
                </div>
                <div 
                  className="object-info-icon"
                  onClick={(e) => handleInfoClick(obj, e)}
                  title="View details"
                >
                  ℹ️
                </div>
                {obj.is_keystone && (
                  <div className="keystone-badge">🔑</div>
                )}
                {auraActive && (
                  <div className="aura-badge" title={auraTooltip}>🌀</div>
                )}
              </div>
            );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
