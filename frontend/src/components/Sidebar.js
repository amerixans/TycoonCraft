import React, { useState } from 'react';
import './Sidebar.css';

function Sidebar({ discoveries, allObjects, eraUnlocks, currentEra, eras }) {
  const [selectedEra, setSelectedEra] = useState(currentEra);
  const [searchTerm, setSearchTerm] = useState('');
  
  const discoveredIds = new Set(discoveries.map(d => d.game_object.id));
  const unlockedEras = new Set(eraUnlocks.map(u => u.era_name));
  
  const objectsByEra = {};
  eras.forEach(era => {
    objectsByEra[era] = allObjects.filter(obj => obj.era_name === era);
  });
  
  const getEraStatus = (era) => {
    if (unlockedEras.has(era)) return 'unlocked';
    if (eras.indexOf(era) <= eras.indexOf(currentEra)) return 'available';
    return 'locked';
  };
  
  // Filter objects based on search term
  const filteredObjects = searchTerm
    ? allObjects.filter(obj => 
        obj.object_name.toLowerCase().includes(searchTerm.toLowerCase()) &&
        discoveredIds.has(obj.id)
      )
    : objectsByEra[selectedEra]?.filter(obj => discoveredIds.has(obj.id)) || [];
  
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
            return (
              <button
                key={era}
                className={`era-tab ${status} ${selectedEra === era ? 'active' : ''}`}
                onClick={() => setSelectedEra(era)}
                disabled={status === 'locked'}
              >
                {era.split(' ')[0]}
              </button>
            );
          })}
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
            filteredObjects.map(obj => (
              <div 
                key={obj.id}
                className={`object-item ${obj.is_keystone ? 'keystone' : ''}`}
                title={obj.flavor_text}
                draggable={true}
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = 'copy';
                  e.dataTransfer.setData('objectId', obj.id.toString());
                  e.dataTransfer.setData('text/plain', obj.object_name);
                }}
              >
                <div className="object-name">
                  {obj.object_name}
                </div>
                <div className="object-stats">
                  <div>💰 {obj.cost}</div>
                  <div>📊 {obj.income_per_second}/s</div>
                </div>
                {obj.is_keystone && (
                  <div className="keystone-badge">🔑</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
