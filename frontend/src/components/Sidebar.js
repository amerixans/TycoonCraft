import React, { useState } from 'react';
import './Sidebar.css';

function Sidebar({ discoveries, allObjects, eraUnlocks, currentEra, eras }) {
  const [selectedEra, setSelectedEra] = useState(currentEra);
  
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
  
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h3>Objects</h3>
      </div>
      
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
      
      <div className="objects-list">
        <h4>{selectedEra}</h4>
        <div className="objects-grid">
          {objectsByEra[selectedEra]?.map(obj => {
            const discovered = discoveredIds.has(obj.id);
            return (
              <div 
                key={obj.id}
                className={`object-item ${!discovered ? 'undiscovered' : ''} ${obj.is_keystone ? 'keystone' : ''}`}
                title={discovered ? obj.flavor_text : '???'}
                draggable={discovered}
                onDragStart={(e) => {
                  if (discovered) {
                    e.dataTransfer.setData('objectId', obj.id);
                  }
                }}
              >
                <div className="object-name">
                  {discovered ? obj.object_name : '???'}
                </div>
                {discovered && (
                  <div className="object-stats">
                    <div>💰 {obj.cost}</div>
                    <div>📊 {obj.income_per_second}/s</div>
                  </div>
                )}
                {obj.is_keystone && discovered && (
                  <div className="keystone-badge">🔑</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
