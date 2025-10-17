import React, { useState, useRef, useEffect } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import './Canvas.css';

const GRID_SIZE = 50; // Pixels per grid tile

// Era-based canvas sizes (height x width in tiles)
const ERA_SIZES = {
  'Hunter-Gatherer': { height: 5, width: 15 },
  'Agriculture': { height: 10, width: 15 },
  'Metallurgy': { height: 10, width: 30 },
  'Steam & Industry': { height: 20, width: 30 },
  'Electric Age': { height: 20, width: 60 },
  'Computing': { height: 40, width: 60 },
  'Futurism': { height: 40, width: 120 },
  'Interstellar': { height: 80, width: 120 },
  'Arcana': { height: 80, width: 240 },
  'Beyond': { height: 160, width: 240 },
};

function Canvas({ placedObjects, discoveries, onPlace, onRemove, currentEra }) {
  const [draggedObject, setDraggedObject] = useState(null);
  const [hoveredPlaced, setHoveredPlaced] = useState(null);
  const transformRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [canvasMode, setCanvasMode] = useState('normal'); // 'normal', 'trash', 'move'
  const [movingObject, setMovingObject] = useState(null);
  
  // Update time every second for build progress
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  
  // Clear hover state if hovered object was removed
  useEffect(() => {
    if (hoveredPlaced && !placedObjects.find(p => p.id === hoveredPlaced.id)) {
      setHoveredPlaced(null);
    }
  }, [placedObjects, hoveredPlaced]);
  
  // Calculate build progress for an object
  const getBuildProgress = (placed) => {
    if (!placed.is_building) return null;
    
    const placedTime = new Date(placed.placed_at).getTime();
    const completeTime = new Date(placed.build_complete_at).getTime();
    const totalDuration = completeTime - placedTime;
    const elapsed = currentTime - placedTime;
    const remaining = Math.max(0, completeTime - currentTime);
    
    return {
      percentage: Math.min(100, Math.max(0, (elapsed / totalDuration) * 100)),
      remainingSeconds: Math.ceil(remaining / 1000)
    };
  };
  
  // Get canvas size for current era
  const canvasSize = ERA_SIZES[currentEra] || ERA_SIZES['Hunter-Gatherer'];
  const CANVAS_WIDTH = canvasSize.width;
  const CANVAS_HEIGHT = canvasSize.height;
  
  // Calculate initial scale to fit canvas nicely (with small padding)
  // Assuming wrapper is around 1200px wide and 600px tall on average
  const wrapperWidth = 1200;
  const wrapperHeight = 600;
  const scaleToFitWidth = wrapperWidth / (CANVAS_WIDTH * GRID_SIZE);
  const scaleToFitHeight = wrapperHeight / (CANVAS_HEIGHT * GRID_SIZE);
  const fitScale = Math.min(scaleToFitWidth, scaleToFitHeight) * 0.95;
  
  // Start significantly more zoomed in
  const initialScale = fitScale + 0.5;
  
  // Calculate minimum scale to prevent empty space
  // Canvas must always fill the viewport completely
  const minScale = Math.min(scaleToFitWidth, scaleToFitHeight);
  
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
    
    if (canvasMode === 'trash') {
      // Trash mode: remove with confirmation
      const refund = Math.floor(placed.game_object.cost * placed.game_object.sellback_pct);
      if (window.confirm(`Remove ${placed.game_object.object_name}? You'll receive ${refund} coins back.`)) {
        setHoveredPlaced(null);
        onRemove(placed.id);
      }
    } else if (canvasMode === 'move') {
      // Move mode: select object for moving
      if (movingObject && movingObject.id === placed.id) {
        // Clicking the same object deselects it
        setMovingObject(null);
      } else {
        setMovingObject(placed);
      }
    } else {
      // Normal mode: show confirmation dialog
      if (window.confirm(`Remove ${placed.game_object.object_name}?`)) {
        setHoveredPlaced(null);
        onRemove(placed.id);
      }
    }
  };
  
  const handleCanvasClick = (e) => {
    if (canvasMode === 'move' && movingObject && e.target.classList.contains('canvas')) {
      // Calculate click position for moving object
      const transformState = transformRef.current?.instance?.transformState;
      if (!transformState) return;
      
      const rect = e.currentTarget.getBoundingClientRect();
      const x = (e.clientX - rect.left) / transformState.scale;
      const y = (e.clientY - rect.top) / transformState.scale;
      
      const gridX = Math.floor(x / GRID_SIZE);
      const gridY = Math.floor(y / GRID_SIZE);
      
      // Check bounds
      if (gridX < 0 || gridY < 0 || 
          gridX + movingObject.game_object.footprint_w > CANVAS_WIDTH || 
          gridY + movingObject.game_object.footprint_h > CANVAS_HEIGHT) {
        alert('⚠️ Out of bounds! Place the object within the grid.');
        return;
      }
      
      // Check for overlap with other objects (excluding the moving object itself)
      const wouldOverlap = placedObjects.some(placed => {
        if (placed.id === movingObject.id) return false;
        return (
          gridX < placed.x + placed.game_object.footprint_w &&
          gridX + movingObject.game_object.footprint_w > placed.x &&
          gridY < placed.y + placed.game_object.footprint_h &&
          gridY + movingObject.game_object.footprint_h > placed.y
        );
      });
      
      if (wouldOverlap) {
        alert('⚠️ Space occupied! Choose another location.');
        return;
      }
      
      // Move the object (we'll need to add an onMove callback)
      // For now, we'll show an alert - the parent component needs to handle this
      alert(`Moving ${movingObject.game_object.object_name} to (${gridX}, ${gridY}) - Feature needs backend support`);
      setMovingObject(null);
    }
  };
  
  return (
    <div className="canvas-container">
      <div className="canvas-header">
        <h3>🗺️ World Map ({CANVAS_HEIGHT}×{CANVAS_WIDTH})</h3>
        <div className="canvas-controls">
          <div className="mode-buttons">
            <button 
              className={`mode-btn ${canvasMode === 'normal' ? 'active' : ''}`}
              onClick={() => {
                setCanvasMode('normal');
                setMovingObject(null);
              }}
              title="Normal Mode"
            >
              👆 Normal
            </button>
            <button 
              className={`mode-btn ${canvasMode === 'move' ? 'active' : ''}`}
              onClick={() => {
                setCanvasMode('move');
                setMovingObject(null);
              }}
              title="Move Mode - Drag objects to reposition"
            >
              ↔️ Move
            </button>
            <button 
              className={`mode-btn trash ${canvasMode === 'trash' ? 'active' : ''}`}
              onClick={() => {
                setCanvasMode('trash');
                setMovingObject(null);
              }}
              title="Trash Mode - Click objects to delete"
            >
              🗑️ Trash
            </button>
          </div>
          <span className="control-hint">🖱️ Drag to pan • 🔍 Scroll to zoom</span>
        </div>
      </div>
      
      <div className="canvas-wrapper">
        <TransformWrapper
          ref={transformRef}
          initialScale={initialScale}
          minScale={minScale}
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
                  className={`canvas ${canvasMode === 'trash' ? 'trash-mode' : ''} ${canvasMode === 'move' ? 'move-mode' : ''}`}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onClick={handleCanvasClick}
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
                      className={`placed-object ${placed.is_building ? 'building' : ''} ${!placed.is_operational ? 'inactive' : ''} ${canvasMode === 'trash' ? 'trashable' : ''} ${canvasMode === 'move' ? 'movable' : ''} ${movingObject && movingObject.id === placed.id ? 'selected-for-move' : ''}`}
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
                      
                      {placed.is_building && (() => {
                        const progress = getBuildProgress(placed);
                        if (!progress) return null;
                        
                        // Calculate circle size based on object footprint
                        const minDimension = Math.min(placed.game_object.footprint_w, placed.game_object.footprint_h);
                        const circleSize = Math.min(minDimension * GRID_SIZE * 0.6, 60);
                        const strokeWidth = Math.max(circleSize * 0.15, 4);
                        const radius = (circleSize - strokeWidth) / 2;
                        const circumference = 2 * Math.PI * radius;
                        const offset = circumference - (progress.percentage / 100) * circumference;
                        
                        return (
                          <div className="building-overlay">
                            <svg 
                              className="building-progress-circle"
                              width={circleSize} 
                              height={circleSize}
                              style={{ width: circleSize, height: circleSize }}
                            >
                              {/* Background circle */}
                              <circle
                                cx={circleSize / 2}
                                cy={circleSize / 2}
                                r={radius}
                                fill="none"
                                stroke="rgba(255, 255, 255, 0.2)"
                                strokeWidth={strokeWidth}
                              />
                              {/* Progress circle */}
                              <circle
                                cx={circleSize / 2}
                                cy={circleSize / 2}
                                r={radius}
                                fill="none"
                                stroke="#27ae60"
                                strokeWidth={strokeWidth}
                                strokeDasharray={circumference}
                                strokeDashoffset={offset}
                                strokeLinecap="round"
                                transform={`rotate(-90 ${circleSize / 2} ${circleSize / 2})`}
                                style={{ transition: 'stroke-dashoffset 0.3s ease' }}
                              />
                            </svg>
                            <div className="building-time" style={{ fontSize: `${Math.max(circleSize * 0.25, 10)}px` }}>
                              {progress.remainingSeconds}s
                            </div>
                          </div>
                        );
                      })()}
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
              <span>🏷️ Category:</span>
              <span className="stat-value">{hoveredPlaced.game_object.category}</span>
            </div>
            <div className="stat-row">
              <span>⭐ Quality:</span>
              <span className="stat-value">{hoveredPlaced.game_object.quality_tier}</span>
            </div>
            <div className="stat-row">
              <span>💰 Income:</span>
              <span className="stat-value">{Math.floor(hoveredPlaced.game_object.income_per_second)}/s</span>
            </div>
            {hoveredPlaced.game_object.time_crystal_generation > 0 && (
              <div className="stat-row">
                <span>💎 Crystals:</span>
                <span className="stat-value">{hoveredPlaced.game_object.time_crystal_generation}/s</span>
              </div>
            )}
            <div className="stat-row">
              <span>⏱️ Duration:</span>
              <span className="stat-value">{Math.floor(hoveredPlaced.game_object.operation_duration_sec / 60)}m {hoveredPlaced.game_object.operation_duration_sec % 60}s</span>
            </div>
            {hoveredPlaced.game_object.build_time_sec > 0 && (
              <div className="stat-row">
                <span>🔨 Build Time:</span>
                <span className="stat-value">{hoveredPlaced.game_object.build_time_sec}s</span>
              </div>
            )}
            <div className="stat-row">
              <span>💵 Sellback:</span>
              <span className="stat-value">{Math.floor(hoveredPlaced.game_object.cost * hoveredPlaced.game_object.sellback_pct)} ({Math.floor(hoveredPlaced.game_object.sellback_pct * 100)}%)</span>
            </div>
            <div className="stat-row">
              <span>🎁 Retire Payout:</span>
              <span className="stat-value">{Math.floor(hoveredPlaced.game_object.cost * hoveredPlaced.game_object.retire_payout_coins_pct)} ({Math.floor(hoveredPlaced.game_object.retire_payout_coins_pct * 100)}%)</span>
            </div>
            <div className="stat-row">
              <span>📊 Status:</span>
              <span className={`stat-value ${hoveredPlaced.is_operational ? 'operational' : 'inactive'}`}>
                {hoveredPlaced.is_building ? '🔨 Building' : hoveredPlaced.is_operational ? '✅ Active' : '⏸️ Inactive'}
              </span>
            </div>
            {hoveredPlaced.is_building && (() => {
              const progress = getBuildProgress(hoveredPlaced);
              return progress ? (
                <div className="stat-row">
                  <span>⏱️ Time Left:</span>
                  <span className="stat-value">{progress.remainingSeconds}s ({Math.round(progress.percentage)}%)</span>
                </div>
              ) : null;
            })()}
            <div className="stat-row">
              <span>📏 Size:</span>
              <span className="stat-value">{hoveredPlaced.game_object.footprint_w}×{hoveredPlaced.game_object.footprint_h}</span>
            </div>
          </div>
          <div className="tooltip-hint">
            {canvasMode === 'normal' ? 'Click to remove' : 
             canvasMode === 'trash' ? 'Click to trash (get sellback)' :
             'Click to select for moving'}
          </div>
        </div>
      )}
    </div>
  );
}

export default Canvas;
