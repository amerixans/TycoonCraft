import React, { useState } from 'react';
import './CraftingArea.css';

function CraftingArea({ discoveries, onCraft, crafting }) {
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
    if (slotA && slotB && !crafting) {
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
        <h3>Crafting</h3>
        <p>Drag objects here to combine them</p>
      </div>
      
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
            <div className="slot-placeholder">Slot A</div>
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
            <div className="slot-placeholder">Slot B</div>
          )}
        </div>
        
        <div className="craft-operator">=</div>
        
        <div className="craft-result">
          {slotA && slotB ? (
            <div className="result-placeholder">?</div>
          ) : (
            <div className="result-empty">Result</div>
          )}
        </div>
      </div>
      
      <button 
        className="craft-button"
        onClick={handleCraft}
        disabled={!slotA || !slotB || crafting}
      >
        {crafting ? (
          <>
            <span className="spinner"></span>
            Crafting...
          </>
        ) : (
          'Craft'
        )}
      </button>
    </div>
  );
}

export default CraftingArea;
