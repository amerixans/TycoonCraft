import React, { useState, useRef } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import './Canvas.css';

const GRID_SIZE = 50; // Pixels per grid tile

// Era-based canvas sizes (height x width in tiles)
const ERA_SIZES = {
  'Hunter-Gatherer': { height: 8, width: 16 },
  'Agriculture': { height: 16, width: 16 },
  'Metallurgy': { height: 16, width: 32 },
  'Steam & Industry': { height: 32, width: 32 },
  'Electric Age': { height: 32, width: 64 },
  'Computing': { height: 64, width: 64 },
  'Futurism': { height: 64, width: 128 },
  'Interstellar': { height: 128, width: 128 },
  'Arcana': { height: 128, width: 256 },
  'Beyond': { height: 256, width: 256 },
};

function Canvas({ placedObjects, discoveries, onPlace, onRemove, currentEra }) {
  const [draggedObject, setDraggedObject] = useState(null);
  const [hoveredPlaced, setHoveredPlaced] = useState(null);
  const transformRef = useRef(null);
  
  // Get canvas size for current era
  const canvasSize = ERA_SIZES[currentEra] || ERA_SIZES['Hunter-Gatherer'];
  const CANVAS_WIDTH = canvasSize.width;
  const CANVAS_HEIGHT = canvasSize.height;
  
  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    
    const objectId = e.dataTransfer.getData('objectId');
    if (!objectId) return;
    
    const obj = discoveries.find(d => d.game_object.id === parseInt(objectId))?.game_object;
    if (!obj) return;
    
    // Get the transform component's current state
    const transformState = transformRef.current?.instance?.transformState;
    if (!transformState) {
      return;
    }
    
    const rect = e.currentTarget.getBoundingClientRect();
    
    // Calculate position accounting for zoom
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    
    // Convert to grid coordinates
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);
    
    setDraggedObject({ obj, x: gridX, y: gridY });
  };
  
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const objectId = e.dataTransfer.getData('objectId');
    
    if (!objectId) {
      setDraggedObject(null);
      return;
    }
    
    const discovery = discoveries.find(d => d.game_object.id === parseInt(objectId));
    
    if (!discovery || !discovery.game_object) {
      setDraggedObject(null);
      return;
    }
    
    const obj = discovery.game_object;
    
    // Get the transform component's current state
    const transformState = transformRef.current?.instance?.transformState;
    if (!transformState) {
      setDraggedObject(null);
      return;
    }
    
    const rect = e.currentTarget.getBoundingClientRect();
    
    // Calculate position accounting for zoom
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    
    // Convert to grid coordinates
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);
    
    // Check bounds
    if (gridX < 0 || gridY < 0 || gridX + obj.footprint_w > CANVAS_WIDTH || gridY + obj.footprint_h > CANVAS_HEIGHT) {
      alert('⚠️ Out of bounds! Place the object within the grid.');
      setDraggedObject(null);
      return;
    }
    
    onPlace(obj.id, gridX, gridY);
    setDraggedObject(null);
  };
  
  const handleDragLeave = (e) => {
    // Only clear if we're leaving the canvas entirely
    if (e.currentTarget === e.target) {
      setDraggedObject(null);
    }
  };
  
  const handlePlacedClick = (placed, e) => {
    e.stopPropagation();
    if (window.confirm(`Remove ${placed.game_object.object_name}?`)) {
      onRemove(placed.id);
    }
  };
  
  return (
    <div className="canvas-container">
      <div className="canvas-header">
        <h3>🗺️ World Map ({CANVAS_HEIGHT}×{CANVAS_WIDTH})</h3>
        <div className="canvas-controls">
          <span className="control-hint">🖱️ Drag to pan • 🔍 Scroll to zoom</span>
        </div>
      </div>
      
      <div className="canvas-wrapper">
        <TransformWrapper
          ref={transformRef}
          initialScale={0.5}
          minScale={0.2}
          maxScale={2}
          centerOnInit={true}
          wheel={{ step: 0.1 }}
          doubleClick={{ disabled: true }}
          panning={{ velocityDisabled: true }}
        >
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              <div className="zoom-controls">
                <button onClick={() => zoomIn()} className="zoom-btn" title="Zoom In">🔍+</button>
                <button onClick={() => zoomOut()} className="zoom-btn" title="Zoom Out">🔍-</button>
                <button onClick={() => resetTransform()} className="zoom-btn" title="Reset View">🎯</button>
              </div>
              
              <TransformComponent
                wrapperStyle={{
                  width: '100%',
                  height: '100%',
                  cursor: draggedObject ? 'crosshair' : 'grab'
                }}
                contentStyle={{
                  width: CANVAS_WIDTH * GRID_SIZE + 'px',
                  height: CANVAS_HEIGHT * GRID_SIZE + 'px',
                }}
              >
                <div
                  className="canvas"
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  style={{
                    width: CANVAS_WIDTH * GRID_SIZE + 'px',
                    height: CANVAS_HEIGHT * GRID_SIZE + 'px',
                    backgroundSize: `${GRID_SIZE}px ${GRID_SIZE}px`,
                  }}
                >
                  {/* Placed objects */}
                  {placedObjects.map(placed => (
                    <div
                      key={placed.id}
                      className={`placed-object ${placed.is_building ? 'building' : ''} ${!placed.is_operational ? 'inactive' : ''}`}
                      style={{
                        left: placed.x * GRID_SIZE + 'px',
                        top: placed.y * GRID_SIZE + 'px',
                        width: placed.game_object.footprint_w * GRID_SIZE + 'px',
                        height: placed.game_object.footprint_h * GRID_SIZE + 'px',
                      }}
                      onClick={(e) => handlePlacedClick(placed, e)}
                      onMouseEnter={() => setHoveredPlaced(placed)}
                      onMouseLeave={() => setHoveredPlaced(null)}
                    >
                      {placed.game_object.image_path ? (
                        <img 
                          src={placed.game_object.image_path} 
                          alt={placed.game_object.object_name}
                          className="object-image"
                        />
                      ) : (
                        <div className="object-placeholder">
                          {placed.game_object.object_name.substring(0, 3).toUpperCase()}
                        </div>
                      )}
                      
                      {placed.is_building && (
                        <div className="building-overlay">
                          <span className="building-icon">🔨</span>
                          <div className="building-progress"></div>
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {/* Ghost preview during drag */}
                  {draggedObject && (
                    <div
                      className="placed-object ghost"
                      style={{
                        left: draggedObject.x * GRID_SIZE + 'px',
                        top: draggedObject.y * GRID_SIZE + 'px',
                        width: draggedObject.obj.footprint_w * GRID_SIZE + 'px',
                        height: draggedObject.obj.footprint_h * GRID_SIZE + 'px',
                      }}
                    >
                      <div className="object-placeholder">
                        {draggedObject.obj.object_name.substring(0, 3).toUpperCase()}
                      </div>
                    </div>
                  )}
                </div>
              </TransformComponent>
            </>
          )}
        </TransformWrapper>
      </div>
      
      {/* Enhanced hover tooltip - fixed position */}
      {hoveredPlaced && (
        <div 
          className="hover-tooltip"
          style={{
            position: 'fixed',
            left: '50%',
            bottom: '20px',
            transform: 'translateX(-50%)',
          }}
        >
          <h4>{hoveredPlaced.game_object.object_name}</h4>
          <p className="tooltip-flavor">{hoveredPlaced.game_object.flavor_text}</p>
          <div className="tooltip-stats">
            <div className="stat-row">
              <span>💰 Income:</span>
              <span className="stat-value">{hoveredPlaced.game_object.income_per_second}/s</span>
            </div>
            {hoveredPlaced.game_object.time_crystal_generation > 0 && (
              <div className="stat-row">
                <span>💎 Crystals:</span>
                <span className="stat-value">{hoveredPlaced.game_object.time_crystal_generation}/s</span>
              </div>
            )}
            <div className="stat-row">
              <span>📊 Status:</span>
              <span className={`stat-value ${hoveredPlaced.is_operational ? 'operational' : 'inactive'}`}>
                {hoveredPlaced.is_building ? '🔨 Building' : hoveredPlaced.is_operational ? '✅ Active' : '⏸️ Inactive'}
              </span>
            </div>
            <div className="stat-row">
              <span>📏 Size:</span>
              <span className="stat-value">{hoveredPlaced.game_object.footprint_w}×{hoveredPlaced.game_object.footprint_h}</span>
            </div>
          </div>
          <div className="tooltip-hint">Click to remove</div>
        </div>
      )}
    </div>
  );
}

export default Canvas;
