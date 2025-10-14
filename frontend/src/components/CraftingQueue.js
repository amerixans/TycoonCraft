import React from 'react';
import './CraftingQueue.css';

function CraftingQueue({ craftingOperations }) {
  if (craftingOperations.length === 0) {
    return null;
  }

  return (
    <div className="crafting-queue-panel">
      <h4>🔄 Active Crafts ({craftingOperations.length})</h4>
      <div className="queue-list">
        {craftingOperations.map(op => (
          <div key={op.id} className={`queue-item ${op.status}`}>
            <div className="queue-content">
              <span className="queue-objects">
                {op.objectA.object_name} + {op.objectB.object_name}
              </span>
              {op.status === 'crafting' && (
                <div className="queue-spinner">
                  <div className="spinner"></div>
                  <span>Crafting...</span>
                </div>
              )}
              {op.status === 'success' && op.result && (
                <div className="queue-result">
                  ✅ {op.result.object.object_name}
                </div>
              )}
              {op.status === 'failed' && (
                <div className="queue-error">
                  ❌ {op.error}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CraftingQueue;
