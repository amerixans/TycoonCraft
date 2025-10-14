import React, { useState } from 'react';
import './CraftingArea.css';

function CraftingArea({ discoveries, onCraft }) {
  const [slotA, setSlotA] = useState(null);
  const [slotB, setSlotB] = useState(null);
  
  const handleDrop = (slot) => (e) => {
    e.preventDefault();
    const objectId = e.dataTransfer.getData('objectId');
    if (!objectId) return;
    
    const obj = discoveries.find(d => d.game_object.id === parseInt(objectId))?.game_object;
    if (!obj) return;
    
    if (slot === 'A') setSlotA(obj);
    else setSlotB(obj);
  };
  
  const handleDragOver = (e) => {
    e.preventDefault();
  };
  
  const handleCraft = () => {
    if (slotA && slotB) {
      onCraft(slotA, slotB);
      setSlotA(null);
      setSlotB(null);
    }
  };
  
  const clearSlot = (slot) => {
    if (slot === 'A') setSlotA(null);
    else setSlotB(null);
  };
  
  return (
    <div className="crafting-area">
      <div className="crafting-header">
        <h3>⚒️ Crafting Workshop</h3>
        <p>Drag two objects to combine them and discover new items!</p>
      </div>
      
      <div className="crafting-main">
        <div className="crafting-slots">
          <div 
            className={`craft-slot ${slotA ? 'filled' : ''}`}
            onDrop={handleDrop('A')}
            onDragOver={handleDragOver}
          >
            {slotA ? (
              <>
                <div className="slot-object">{slotA.object_name}</div>
                <button className="clear-slot" onClick={() => clearSlot('A')}>✕</button>
              </>
            ) : (
              <div className="slot-placeholder">
                <span className="slot-icon">📦</span>
                <span>Slot A</span>
              </div>
            )}
          </div>
          
          <div className="craft-operator">+</div>
          
          <div 
            className={`craft-slot ${slotB ? 'filled' : ''}`}
            onDrop={handleDrop('B')}
            onDragOver={handleDragOver}
          >
            {slotB ? (
              <>
                <div className="slot-object">{slotB.object_name}</div>
                <button className="clear-slot" onClick={() => clearSlot('B')}>✕</button>
              </>
            ) : (
              <div className="slot-placeholder">
                <span className="slot-icon">📦</span>
                <span>Slot B</span>
              </div>
            )}
          </div>
          
          <div className="craft-operator">=</div>
          
          <div className="craft-result">
            {slotA && slotB ? (
              <div className="result-placeholder">
                <span className="result-icon">❓</span>
                <span className="result-text">Mystery!</span>
              </div>
            ) : (
              <div className="result-empty">
                <span className="result-icon">✨</span>
                <span className="result-text">Result</span>
              </div>
            )}
          </div>
        </div>
        
        <button 
          className="craft-button"
          onClick={handleCraft}
          disabled={!slotA || !slotB}
        >
          ⚒️ Craft Now!
        </button>
      </div>
    </div>
  );
}

export default CraftingArea;
