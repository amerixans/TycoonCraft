import React, { useState, useEffect } from 'react';
import { formatNumber } from '../utils/formatNumber';
import { ERAS, ERA_CRAFTING_COSTS } from '../config';
import './CraftingArea.css';

function CraftingArea({ discoveries, onCraft, playerCoins }) {
  const [slotA, setSlotA] = useState(null);
  const [slotB, setSlotB] = useState(null);
  const [craftingCost, setCraftingCost] = useState(0);
  const [eraMismatch, setEraMismatch] = useState(false);
  
  useEffect(() => {
    if (slotA && slotB) {
      // Check for era mismatch
      if (slotA.era_name !== slotB.era_name) {
        setEraMismatch(true);
        setCraftingCost(0);
      } else {
        setEraMismatch(false);
        // Calculate crafting cost based on higher era
        const indexA = ERAS.indexOf(slotA.era_name);
        const indexB = ERAS.indexOf(slotB.era_name);
        const higherEraIndex = Math.max(indexA, indexB);
        const higherEra = ERAS[higherEraIndex];
        const cost = ERA_CRAFTING_COSTS[higherEra] || 50;
        setCraftingCost(cost);
      }
    } else {
      setCraftingCost(0);
      setEraMismatch(false);
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
    if (slot === 'A') {
      setSlotA(null);
      // Reset era mismatch if we're clearing a slot
      if (slotB) {
        setEraMismatch(false);
      }
    } else {
      setSlotB(null);
      // Reset era mismatch if we're clearing a slot
      if (slotA) {
        setEraMismatch(false);
      }
    }
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
                <div className="slot-content">
                  {slotA.image_path ? (
                    <img
                      src={slotA.image_path}
                      alt={slotA.object_name}
                      className="slot-image"
                    />
                  ) : (
                    <div className="slot-image-placeholder">
                      {slotA.object_name.substring(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div className="slot-object">{slotA.object_name}</div>
                </div>
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
                <div className="slot-content">
                  {slotB.image_path ? (
                    <img
                      src={slotB.image_path}
                      alt={slotB.object_name}
                      className="slot-image"
                    />
                  ) : (
                    <div className="slot-image-placeholder">
                      {slotB.object_name.substring(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div className="slot-object">{slotB.object_name}</div>
                </div>
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
        
        {eraMismatch && (
          <div className="era-mismatch-warning">
            ⚠️ Cannot combine items from different eras! {slotA.object_name} is from {slotA.era_name}, but {slotB.object_name} is from {slotB.era_name}. Only items from the same era can be combined.
          </div>
        )}
        
        <button 
          className={`craft-button ${slotA && slotB && !canAffordCraft ? 'insufficient' : ''} ${eraMismatch ? 'era-mismatch' : ''}`}
          onClick={handleCraft}
          disabled={!slotA || !slotB || !canAffordCraft || eraMismatch}
        >
          {!slotA || !slotB ? (
            '⚒️ Craft Now!'
          ) : eraMismatch ? (
            '⚠️ Era Mismatch!'
          ) : canAffordCraft ? (
            `⚒️ Craft Now! (💰 ${formatNumber(craftingCost)} coins)`
          ) : (
            `⚒️ Craft Now! (💰 ${formatNumber(craftingCost)} coins - Insufficient!)`
          )}
        </button>
      </div>
    </div>
  );
}

export default CraftingArea;
