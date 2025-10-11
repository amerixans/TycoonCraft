import React, { useState, useRef } from 'react';
import './Canvas.css';

const GRID_SIZE = 10; // Visual grid cell size in pixels
const CANVAS_SIZE = 1000; // Logical canvas size in tiles

function Canvas({ placedObjects, discoveries, onPlace, onRemove }) {
  const [draggedObject, setDraggedObject] = useState(null);
  const [hoveredPlaced, setHoveredPlaced] = useState(null);
  const canvasRef = useRef(null);
  
  const handleDrop = (e) => {
    e.preventDefault();
    
    const objectId = e.dataTransfer.getData('objectId');
    if (!objectId) return;
    
    const obj = discoveries.find(d => d.game_object.id === parseInt(objectId))?.game_object;
    if (!obj) return;
    
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / GRID_SIZE);
    const y = Math.floor((e.clientY - rect.top) / GRID_SIZE);
    
    // Check bounds
    if (x < 0 || y < 0 || x + obj.footprint_w > CANVAS_SIZE || y + obj.footprint_h > CANVAS_SIZE) {
      alert('Out of bounds!');
      return;
    }
    
    onPlace(obj.id, x, y);
    setDraggedObject(null);
  };
  
  const handleDragOver = (e) => {
    e.preventDefault();
    
    const objectId = e.dataTransfer.getData('objectId');
    if (!objectId) return;
    
    const obj = discoveries.find(d => d.game_object.id === parseInt(objectId))?.game_object;
    if (!obj) return;
    
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / GRID_SIZE);
    const y = Math.floor((e.clientY - rect.top) / GRID_SIZE);
    
    setDraggedObject({ obj, x, y });
  };
  
  const handleDragLeave = () => {
    setDraggedObject(null);
  };
  
  const handlePlacedClick = (placed) => {
    if (window.confirm(`Remove ${placed.game_object.object_name}?`)) {
      onRemove(placed.id);
    }
  };
  
  return (
    <div className="canvas-container">
      <div className="canvas-header">
        <h3>Canvas</h3>
        <p>Drag objects here to place them</p>
      </div>
      
      <div 
        ref={canvasRef}
        className="canvas"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{
          width: CANVAS_SIZE * GRID_SIZE / 10 + 'px',
          height: CANVAS_SIZE * GRID_SIZE / 10 + 'px',
        }}
      >
        {/* Grid background */}
        <div className="canvas-grid"></div>
        
        {/* Placed objects */}
        {placedObjects.map(placed => (
          <div
            key={placed.id}
            className={`placed-object ${placed.is_building ? 'building' : ''} ${!placed.is_operational ? 'inactive' : ''}`}
            style={{
              left: placed.x * GRID_SIZE / 10 + 'px',
              top: placed.y * GRID_SIZE / 10 + 'px',
              width: placed.game_object.footprint_w * GRID_SIZE / 10 + 'px',
              height: placed.game_object.footprint_h * GRID_SIZE / 10 + 'px',
            }}
            onClick={() => handlePlacedClick(placed)}
            onMouseEnter={() => setHoveredPlaced(placed)}
            onMouseLeave={() => setHoveredPlaced(null)}
            title={placed.game_object.object_name}
          >
            {placed.game_object.image_path ? (
              <img 
                src={placed.game_object.image_path} 
                alt={placed.game_object.object_name}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              <div className="object-placeholder">
                {placed.game_object.object_name.substring(0, 2).toUpperCase()}
              </div>
            )}
            
            {placed.is_building && (
              <div className="building-overlay">🔨</div>
            )}
          </div>
        ))}
        
        {/* Ghost preview during drag */}
        {draggedObject && (
          <div
            className="placed-object ghost"
            style={{
              left: draggedObject.x * GRID_SIZE / 10 + 'px',
              top: draggedObject.y * GRID_SIZE / 10 + 'px',
              width: draggedObject.obj.footprint_w * GRID_SIZE / 10 + 'px',
              height: draggedObject.obj.footprint_h * GRID_SIZE / 10 + 'px',
            }}
          >
            <div className="object-placeholder">
              {draggedObject.obj.object_name.substring(0, 2).toUpperCase()}
            </div>
          </div>
        )}
      </div>
      
      {/* Hover tooltip */}
      {hoveredPlaced && (
        <div className="hover-tooltip">
          <h4>{hoveredPlaced.game_object.object_name}</h4>
          <p>{hoveredPlaced.game_object.flavor_text}</p>
          <div className="tooltip-stats">
            <div>💰 Income: {hoveredPlaced.game_object.income_per_second}/s</div>
            {hoveredPlaced.game_object.time_crystal_generation > 0 && (
              <div>💎 Crystals: {hoveredPlaced.game_object.time_crystal_generation}/s</div>
            )}
            <div>Status: {hoveredPlaced.is_building ? 'Building' : hoveredPlaced.is_operational ? 'Operational' : 'Inactive'}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Canvas;
