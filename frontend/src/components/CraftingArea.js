import React, { useState, useEffect } from 'react';
import './CraftingArea.css';

const ERA_CRAFTING_COSTS = {
  'Hunter-Gatherer': 50,
  'Agriculture': 250,
  'Metallurgy': 1250,
  'Steam & Industry': 6250,
  'Electric Age': 31250,
  'Computing': 156250,
  'Futurism': 781250,
  'Interstellar': 3906250,
  'Arcana': 19531250,
  'Beyond': 97656250,
};

const ERAS = [
  'Hunter-Gatherer', 'Agriculture', 'Metallurgy', 'Steam & Industry',
  'Electric Age', 'Computing', 'Futurism', 'Interstellar', 'Arcana', 'Beyond'
];

function CraftingArea({ discoveries, onCraft, playerCoins }) {
  const [slotA, setSlotA] = useState(null);
  const [slotB, setSlotB] = useState(null);
  const [craftingCost, setCraftingCost] = useState(0);
  
  useEffect(() => {
    if (slotA && slotB) {
      // Calculate crafting cost based on higher era
      const indexA = ERAS.indexOf(slotA.era_name);
      const indexB = ERAS.indexOf(slotB.era_name);
      const higherEraIndex = Math.max(indexA, indexB);
      const higherEra = ERAS[higherEraIndex];
      const cost = ERA_CRAFTING_COSTS[higherEra] || 50;
      setCraftingCost(cost);
    } else {
      setCraftingCost(0);
    }
  }, [slotA, slotB]);
  
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
  
  const canAffordCraft = playerCoins >= craftingCost;
  
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
        
        {slotA && slotB && (
          <div className="crafting-cost-display">
            <span className="cost-label">Crafting Cost:</span>
            <span className={`cost-value ${canAffordCraft ? 'can-afford' : 'cannot-afford'}`}>
              💰 {craftingCost}
            </span>
            {!canAffordCraft && (
              <span className="insufficient-funds">Insufficient coins!</span>
            )}
          </div>
        )}
        
        <button 
          className="craft-button"
          onClick={handleCraft}
          disabled={!slotA || !slotB || !canAffordCraft}
        >
          ⚒️ Craft Now! {slotA && slotB && `(${craftingCost} coins)`}
        </button>
      </div>
    </div>
  );
}

export default CraftingArea;
