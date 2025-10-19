import React, { useState, useRef, useEffect } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { formatNumber } from '../utils/formatNumber';
import { hasAura, describeAuraModifier, calculateCategoryMultipliers } from '../utils/aura';
import './Canvas.css';

const GRID_SIZE = 50; // Pixels per grid tile

// Era-based canvas sizes (height x width in tiles)
// Starting at 3x9 for Hunter-Gatherer, doubling each era unlock
const ERA_SIZES = {
  'Hunter-Gatherer': { height: 5, width: 15 },
  'Agriculture': { height: 10, width: 30 },
  'Metallurgy': { height: 20, width: 60 },
  'Steam & Industry': { height: 40, width: 120 },
  'Electric Age': { height: 80, width: 240 },
  'Computing': { height: 160, width: 480 },
  'Futurism': { height: 320, width: 960 },
  'Interstellar': { height: 640, width: 1920 },
  'Arcana': { height: 1280, width: 3840 },
  'Beyond': { height: 2560, width: 7680 },
};

function Canvas({ placedObjects, discoveries, onPlace, onRemove, onMove, currentEra, auraModifierMap }) {
  const [draggedObject, setDraggedObject] = useState(null);
  const [hoveredPlaced, setHoveredPlaced] = useState(null);
  const transformRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const wrapperRef = useRef(null);
  const [wrapperSize, setWrapperSize] = useState({ width: 0, height: 0 });
  const [transformKey, setTransformKey] = useState(0);
  const previousScaleRef = useRef(1);
  const previousEraRef = useRef(currentEra);
  const [canvasMode, setCanvasMode] = useState('view'); // 'view', 'move', 'trash'
  const [movingObject, setMovingObject] = useState(null);

  const formatDuration = (seconds) => {
    const totalSeconds = Number(seconds);
    if (Number.isNaN(totalSeconds) || totalSeconds <= 0) return '0s';
    if (totalSeconds < 60) return `${Math.round(totalSeconds)}s`;
    if (totalSeconds < 3600) return `${Math.round(totalSeconds / 60)}m`;
    if (totalSeconds < 86400) return `${Math.round(totalSeconds / 3600)}h`;
    return `${Math.round(totalSeconds / 86400)}d`;
  };

  const getPlacementPreview = (gameObject) => {
    if (!gameObject) return null;

    const category = gameObject.category;
    const baseBuildTime = Number(gameObject.build_time_sec ?? gameObject.build_time ?? 0);
    const baseDuration = Number(
      gameObject.operation_duration_sec ?? gameObject.operation_duration ?? 0
    );

    const multipliers = calculateCategoryMultipliers(
      auraModifierMap instanceof Map ? auraModifierMap : new Map(),
      category
    );

    const buildMultiplier = Number(multipliers.build_time_multiplier ?? 1);
    const durationMultiplier = Number(multipliers.operation_duration_multiplier ?? 1);

    return {
      baseBuildTime,
      baseDuration,
      effectiveBuildTime: Math.max(0, Math.round(baseBuildTime * buildMultiplier)),
      effectiveDuration: Math.max(0, Math.round(baseDuration * durationMultiplier)),
      buildMultiplier,
      durationMultiplier,
    };
  };
  
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

  // Track wrapper size so we can derive a zoom level that covers the viewport.
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const updateSize = () => {
      const { clientWidth, clientHeight } = wrapper;
      setWrapperSize((prev) => {
        if (prev.width === clientWidth && prev.height === clientHeight) {
          return prev;
        }
        return { width: clientWidth, height: clientHeight };
      });
    };

    updateSize();

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => updateSize());
      observer.observe(wrapper);
      return () => observer.disconnect();
    } else {
      window.addEventListener('resize', updateSize);
      return () => window.removeEventListener('resize', updateSize);
    }
  }, []);
  
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

  // Calculate retirement progress for an operational object
  const getRetirementProgress = (placed) => {
    if (!placed.is_operational || placed.retire_at === null) return null;

    const buildCompleteTime = new Date(placed.build_complete_at).getTime();
    const retireTime = new Date(placed.retire_at).getTime();
    const totalDuration = retireTime - buildCompleteTime;
    const elapsed = currentTime - buildCompleteTime;
    const remaining = Math.max(0, retireTime - currentTime);

    return {
      percentage: Math.min(100, Math.max(0, (elapsed / totalDuration) * 100)),
      remainingSeconds: Math.ceil(remaining / 1000),
      isRetiring: remaining <= 0
    };
  };

  // Get border status class based on retirement progress
  const getOperationalStatus = (placed) => {
    if (!placed.is_operational || placed.retire_at === null) return '';

    const retireProgress = getRetirementProgress(placed);
    if (!retireProgress) return '';

    // Critical: 10% or less remaining (90%+ elapsed)
    if (retireProgress.percentage >= 90) return 'operational-critical';
    // Warning: 25% or less remaining (75%+ elapsed)
    if (retireProgress.percentage >= 75) return 'operational-warning';
    // Healthy: more than 25% remaining
    return 'operational-healthy';
  };
  
  // Get canvas size for current era
  const canvasSize = ERA_SIZES[currentEra] || ERA_SIZES['Hunter-Gatherer'];
  const CANVAS_WIDTH = canvasSize.width;
  const CANVAS_HEIGHT = canvasSize.height;
  const contentWidth = CANVAS_WIDTH * GRID_SIZE;
  const contentHeight = CANVAS_HEIGHT * GRID_SIZE;

  let desiredScale = 1;
  let minScale = 0.2; // Default fallback

  if (wrapperSize.width && wrapperSize.height) {
    const widthRatio = wrapperSize.width / contentWidth;
    const heightRatio = wrapperSize.height / contentHeight;
    const needsWidthScale = contentWidth < wrapperSize.width;
    const needsHeightScale = contentHeight < wrapperSize.height;

    if (needsWidthScale || needsHeightScale) {
      desiredScale = Math.max(
        needsWidthScale ? widthRatio : 1,
        needsHeightScale ? heightRatio : 1
      );
    }

    // Set minScale to ensure canvas always fills the viewport
    // Users can't zoom out beyond the point where canvas edges are visible
    minScale = Math.min(widthRatio, heightRatio);
  }

  useEffect(() => {
    const scaleChanged = Math.abs(desiredScale - previousScaleRef.current) > 0.01;
    const eraChanged = previousEraRef.current !== currentEra;

    if (scaleChanged || eraChanged) {
      previousScaleRef.current = desiredScale;
      previousEraRef.current = currentEra;
      setTransformKey((prev) => prev + 1);
    }
  }, [desiredScale, currentEra]);
  
  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';

    const objectId = e.dataTransfer.getData('objectId');
    if (!objectId) return;

    // Handle dragging from sidebar
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
      // Delete immediately without confirmation
      setHoveredPlaced(null);
      onRemove(placed.id);
    } else if (canvasMode === 'move') {
      // Start moving the object
      setMovingObject(placed);
      setDraggedObject({
        obj: placed.game_object,
        x: placed.x,
        y: placed.y
      });
    }
    // In 'view' mode, do nothing on click
  };

  const handleCanvasMouseMove = (e) => {
    if (!movingObject) return;

    const transformState = transformRef.current?.instance?.transformState;
    if (!transformState) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);

    setDraggedObject({
      obj: movingObject.game_object,
      x: gridX,
      y: gridY
    });
  };

  const handleCanvasMouseUp = (e) => {
    if (!movingObject) return;

    e.preventDefault();
    e.stopPropagation();

    const transformState = transformRef.current?.instance?.transformState;
    if (!transformState) {
      setMovingObject(null);
      setDraggedObject(null);
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / transformState.scale;
    const y = (e.clientY - rect.top) / transformState.scale;
    const gridX = Math.floor(x / GRID_SIZE);
    const gridY = Math.floor(y / GRID_SIZE);

    const obj = movingObject.game_object;

    // Check bounds
    if (gridX < 0 || gridY < 0 || gridX + obj.footprint_w > CANVAS_WIDTH || gridY + obj.footprint_h > CANVAS_HEIGHT) {
      alert('⚠️ Out of bounds! Place the object within the grid.');
      setMovingObject(null);
      setDraggedObject(null);
      return;
    }

    // Use the move endpoint to preserve object state (build progress, etc.)
    onMove(movingObject.id, gridX, gridY);
    setMovingObject(null);
    setDraggedObject(null);
  };
  
  return (
    <div className="canvas-container">
      <div className="canvas-header">
        <h3>🗺️ World Map ({CANVAS_HEIGHT}×{CANVAS_WIDTH})</h3>
        <div className="canvas-controls">
          <button
            className={`mode-btn ${canvasMode === 'view' ? 'active' : ''}`}
            onClick={() => {
              setCanvasMode('view');
              setMovingObject(null);
            }}
            title="View Mode"
          >
            👁️ View
          </button>
          <button
            className={`mode-btn ${canvasMode === 'move' ? 'active' : ''}`}
            onClick={() => {
              setCanvasMode('move');
              setMovingObject(null);
            }}
            title="Move Mode"
          >
            ✋ Move
          </button>
          <button
            className={`mode-btn ${canvasMode === 'trash' ? 'active' : ''}`}
            onClick={() => {
              setCanvasMode('trash');
              setMovingObject(null);
            }}
            title="Delete Mode"
          >
            ❌ Remove
          </button>
          <span className="control-hint">🖱️ Drag to pan • 🔍 Scroll to zoom</span>
        </div>
      </div>
      
      <div className="canvas-wrapper" ref={wrapperRef}>
        <TransformWrapper
          key={transformKey}
          ref={transformRef}
          initialScale={desiredScale}
          minScale={minScale}
          maxScale={10}
          centerOnInit={true}
          centerZoomedOut={true}
          limitToBounds={true}
          wheel={{ step: 0.1 }}
          doubleClick={{ disabled: true }}
          panning={{ disabled: canvasMode === 'move' || canvasMode === 'trash', velocityDisabled: true }}
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
                  cursor: draggedObject || movingObject ? 'crosshair' : canvasMode === 'move' ? 'move' : canvasMode === 'trash' ? 'not-allowed' : 'grab'
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
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                  style={{
                    width: CANVAS_WIDTH * GRID_SIZE + 'px',
                    height: CANVAS_HEIGHT * GRID_SIZE + 'px',
                    backgroundSize: `${GRID_SIZE}px ${GRID_SIZE}px`,
                  }}
                >
                  {/* Placed objects */}
                  {placedObjects.map(placed => {
                    const auraActive = hasAura(placed.game_object);
                    const auraTooltip = auraActive
                      ? placed.game_object.global_modifiers
                          .map((modifier) => {
                            const details = describeAuraModifier(modifier);
                            const effectText =
                              details.effects.length > 0
                                ? details.effects.join(', ')
                                : 'No stat changes';
                            return `${details.categories}: ${effectText} (${details.activation})`;
                          })
                          .join('\\n')
                      : '';

                    return (
                    <div
                      key={placed.id}
                      className={`placed-object ${placed.is_building ? 'building' : (!placed.is_operational ? 'retiring' : getOperationalStatus(placed))}`}
                      style={{
                        left: placed.x * GRID_SIZE + 'px',
                        top: placed.y * GRID_SIZE + 'px',
                        width: placed.game_object.footprint_w * GRID_SIZE + 'px',
                        height: placed.game_object.footprint_h * GRID_SIZE + 'px',
                        cursor: canvasMode === 'trash' ? 'not-allowed' : canvasMode === 'move' ? 'move' : 'pointer',
                        opacity: movingObject && movingObject.id === placed.id ? 0.3 : 1,
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

                      {auraActive && (
                        <div className="placed-aura-badge" title={auraTooltip}>🌀</div>
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
                                stroke="rgba(255,255,255,0.15)"
                                strokeWidth={strokeWidth}
                                fill="none"
                              />

                              {/* Progress circle */}
                              <circle
                                cx={circleSize / 2}
                                cy={circleSize / 2}
                                r={radius}
                                stroke="var(--accent-secondary)"
                                strokeWidth={strokeWidth}
                                fill="none"
                                strokeDasharray={`${circumference} ${circumference}`}
                                strokeDashoffset={offset}
                                strokeLinecap="round"
                              />

                              {/* Progress text */}
                              <text
                                x="50%"
                                y="50%"
                                dominantBaseline="middle"
                                textAnchor="middle"
                                fill="var(--text-primary)"
                                fontSize={Math.max(circleSize * 0.25, 12)}
                                fontWeight="bold"
                              >
                                {Math.round(progress.percentage)}%
                              </text>
                            </svg>
                            <div className="building-remaining">
                              {progress.remainingSeconds > 60
                                ? `${Math.ceil(progress.remainingSeconds / 60)}m`
                                : `${progress.remainingSeconds}s`}
                            </div>
                          </div>
                        );
                      })()}

                      {(!placed.is_building && placed.is_operational && placed.retire_at !== null) && (() => {
                        const progress = getRetirementProgress(placed);
                        if (!progress) return null;

                        const minDimension = Math.min(placed.game_object.footprint_w, placed.game_object.footprint_h);

                        return (
                          <div className={`retirement-badge ${progress.isRetiring ? 'retirement-critical' : ''}`}>
                            <div className="retirement-label">⏳</div>
                            <div className="retirement-remaining">
                              {progress.remainingSeconds > 60
                                ? `${Math.ceil(progress.remainingSeconds / 60)}m`
                                : `${progress.remainingSeconds}s`}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  );
                  })}
                  
                  {/* Ghost preview during drag */}
                  {draggedObject && (() => {
                    const preview = getPlacementPreview(draggedObject.obj);
                    return (
                      <div
                        className="placed-object ghost"
                        style={{
                          left: draggedObject.x * GRID_SIZE + 'px',
                          top: draggedObject.y * GRID_SIZE + 'px',
                          width: draggedObject.obj.footprint_w * GRID_SIZE + 'px',
                          height: draggedObject.obj.footprint_h * GRID_SIZE + 'px',
                        }}
                      >
                        {draggedObject.obj.image_path ? (
                          <img
                            src={draggedObject.obj.image_path}
                            alt={draggedObject.obj.object_name}
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                          />
                        ) : (
                          <div className="object-placeholder">
                            {draggedObject.obj.object_name.substring(0, 3).toUpperCase()}
                          </div>
                        )}

                        {preview && (
                          <div className="placement-preview">
                            {preview.baseBuildTime > 0 && (
                              <div className="placement-preview-row">
                                <span>🔨 Build</span>
                                <span>
                                  {formatDuration(preview.baseBuildTime)}
                                  {preview.buildMultiplier !== 1 && (
                                    <>
                                      {' '}
                                      → {formatDuration(preview.effectiveBuildTime)}
                                    </>
                                  )}
                                </span>
                              </div>
                            )}
                            {preview.baseDuration > 0 && (
                              <div className="placement-preview-row">
                                <span>⏱️ Lifespan</span>
                                <span>
                                  {formatDuration(preview.baseDuration)}
                                  {preview.durationMultiplier !== 1 && (
                                    <>
                                      {' '}
                                      → {formatDuration(preview.effectiveDuration)}
                                    </>
                                  )}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </TransformComponent>
            </>
          )}
        </TransformWrapper>
      </div>
      
      {/* Enhanced hover tooltip - fixed position */}
      {hoveredPlaced && canvasMode === 'view' && (
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
              <span className="stat-value">{!hoveredPlaced.is_operational ? '0' : formatNumber(hoveredPlaced.game_object.income_per_second)}/s</span>
            </div>
            {hoveredPlaced.game_object.time_crystal_generation > 0 && (
              <div className="stat-row">
                <span>💎 Crystals:</span>
                <span className="stat-value">{formatNumber(hoveredPlaced.game_object.time_crystal_generation)}/s</span>
              </div>
            )}
            <div className="stat-row">
              <span>📊 Status:</span>
              <span className={`stat-value ${hoveredPlaced.is_operational ? 'operational' : 'inactive'}`}>
                {hoveredPlaced.is_building ? '🔨 Building' : hoveredPlaced.is_operational ? '✅ Active' : '⏸️ Retired'}
              </span>
            </div>
            {hoveredPlaced.is_building && (() => {
              const progress = getBuildProgress(hoveredPlaced);
              return progress ? (
                <div className="stat-row">
                  <span>⏱️ Building:</span>
                  <span className="stat-value">{progress.remainingSeconds}s ({Math.round(progress.percentage)}%)</span>
                </div>
              ) : null;
            })()}
{hoveredPlaced.is_operational && hoveredPlaced.retire_at && (() => {
              const retireProgress = getRetirementProgress(hoveredPlaced);
              if (!retireProgress) return null;

              // Format time remaining
              const formatTime = (seconds) => {
                if (seconds < 60) return `${seconds}s`;
                if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
                const hours = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                return `${hours}h ${mins}m`;
              };

              return (
                <div className="stat-row">
                  <span>⏳ Time Left:</span>
                  <span className="stat-value">{formatTime(retireProgress.remainingSeconds)}</span>
                </div>
              );
            })()}
            <div className="stat-row">
              <span>📏 Size:</span>
              <span className="stat-value">{hoveredPlaced.game_object.footprint_w}×{hoveredPlaced.game_object.footprint_h}</span>
            </div>
            {/* Show removal refund for operational or retired objects */}
            {(!hoveredPlaced.is_building) && (
              <div className="stat-row">
                <span>💵 Remove for:</span>
                <span className="stat-value">
                  {hoveredPlaced.is_operational
                    ? formatNumber(hoveredPlaced.game_object.cost * hoveredPlaced.game_object.sellback_pct)
                    : formatNumber(hoveredPlaced.game_object.cost * hoveredPlaced.game_object.retire_payout_coins_pct)
                  } coins
                </span>
              </div>
            )}
            {hasAura(hoveredPlaced.game_object) && (
              <div className="tooltip-auras">
                <div className="tooltip-auras-title">Aura Effects</div>
                <ul>
                  {hoveredPlaced.game_object.global_modifiers.map((modifier, idx) => {
                    const details = describeAuraModifier(modifier);
                    const effects = details.effects.length > 0
                      ? details.effects.join(', ')
                      : 'No stat changes';
                    return (
                      <li key={idx}>{details.categories}: {effects}</li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Canvas;
