import React, { useState, useRef } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import './Canvas.css';

const GRID_SIZE = 50; // Pixels per grid tile (increased for better visibility)
const CANVAS_SIZE = 1000; // Logical canvas size in tiles

function Canvas({ placedObjects, discoveries, onPlace, onRemove }) {
  const [draggedObject, setDraggedObject] = useState(null);
  const [hoveredPlaced, setHoveredPlaced] = useState(null);
  const transformRef = useRef(null);
  
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
      console.log('No transform state in dragOver');
      return;
    }
    
    const rect = e.currentTarget.getBoundingClientRect();
    
    // Calculate position accounting for zoom
    // getBoundingClientRect() already accounts for the pan (translate), so we only divide by scale
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    
    // Convert to grid coordinates
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);
    
    console.log('DragOver - Client:', e.clientX, e.clientY, 'Rect:', rect.left, rect.top, 'Scale:', transformState.scale, 'Grid:', gridX, gridY);
    
    setDraggedObject({ obj, x: gridX, y: gridY });
  };
  
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const objectId = e.dataTransfer.getData('objectId');
    console.log('Drop event - objectId:', objectId);
    
    if (!objectId) {
      console.log('No objectId found in drop event');
      setDraggedObject(null);
      return;
    }
    
    const discovery = discoveries.find(d => d.game_object.id === parseInt(objectId));
    console.log('Found discovery:', discovery);
    
    if (!discovery || !discovery.game_object) {
      console.log('No discovery or game_object found');
      setDraggedObject(null);
      return;
    }
    
    const obj = discovery.game_object;
    
    // Get the transform component's current state
    const transformState = transformRef.current?.instance?.transformState;
    if (!transformState) {
      console.log('No transform state - ref:', transformRef.current);
      setDraggedObject(null);
      return;
    }
    
    const rect = e.currentTarget.getBoundingClientRect();
    
    // Calculate position accounting for zoom
    // getBoundingClientRect() already accounts for the pan (translate), so we only divide by scale
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    
    // Convert to grid coordinates
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);
    
    console.log('Drop at client:', e.clientX, e.clientY);
    console.log('Rect position:', rect.left, rect.top);
    console.log('Transform state:', { scale: transformState.scale, posX: transformState.positionX, posY: transformState.positionY });
    console.log('Calculated position:', { x, y, gridX, gridY, footprint: [obj.footprint_w, obj.footprint_h] });
    
    // Check bounds
    if (gridX < 0 || gridY < 0 || gridX + obj.footprint_w > CANVAS_SIZE || gridY + obj.footprint_h > CANVAS_SIZE) {
      alert('⚠️ Out of bounds! Place the object within the grid.');
      setDraggedObject(null);
      return;
    }
    
    console.log('Calling onPlace with:', obj.id, gridX, gridY);
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
        <h3>🗺️ World Map</h3>
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
                  width: CANVAS_SIZE * GRID_SIZE + 'px',
                  height: CANVAS_SIZE * GRID_SIZE + 'px',
                }}
              >
                <div
                  className="canvas"
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  style={{
                    width: CANVAS_SIZE * GRID_SIZE + 'px',
                    height: CANVAS_SIZE * GRID_SIZE + 'px',
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
