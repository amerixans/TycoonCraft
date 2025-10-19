import React from 'react';
import './CraftingResults.css';

function CraftingResults({ craftingResults }) {
  if (craftingResults.length === 0) {
    return null;
  }

  return (
    <div className="crafting-results-panel">
      <h4>✨ Discovered!</h4>
      <div className="results-list">
        {craftingResults.map((result) => (
          <div key={result.id} className="result-item">
            {result.object.image_path && (
              <img
                src={result.object.image_path}
                alt={result.object.object_name}
                className="result-image"
              />
            )}
            <div className="result-name">{result.object.object_name}</div>
            {result.object.flavor_text && (
              <div className="result-flavor">{result.object.flavor_text}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default CraftingResults;
