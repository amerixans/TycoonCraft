import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { formatMultiplier } from '../utils/aura';
import './AuraSummary.css';

const AuraSummary = ({ summary, highlightedCategory }) => {
  const [expandedCategories, setExpandedCategories] = useState({});

  const toggleExpanded = (category) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  if (!summary?.length) {
    return (
      <div className="aura-summary aura-summary-empty">
        <span>No active auras yet. Place aura buildings to boost your empire!</span>
      </div>
    );
  }

  return (
    <div className="aura-summary">
      <div className="aura-summary-header">
        <span>🔮 Active Auras</span>
        <small>Summarised by category</small>
      </div>
      <div className="aura-summary-list">
        {summary.map((entry) => {
          const {
            category,
            income_multiplier,
            build_time_multiplier,
            operation_duration_multiplier,
            sources = [],
          } = entry;

          const effects = [];
          if (Math.abs((income_multiplier ?? 1) - 1) >= 0.001) {
            effects.push(`Income ${formatMultiplier(income_multiplier, Math.abs(income_multiplier - 1) < 0.1 ? 1 : 0)}`);
          }
          if (Math.abs((build_time_multiplier ?? 1) - 1) >= 0.001) {
            effects.push(`Build time ${formatMultiplier(build_time_multiplier, Math.abs(build_time_multiplier - 1) < 0.1 ? 1 : 0)}`);
          }
          if (
            Math.abs((operation_duration_multiplier ?? 1) - 1) >= 0.001
          ) {
            effects.push(
              `Lifespan ${formatMultiplier(operation_duration_multiplier, Math.abs(operation_duration_multiplier - 1) < 0.1 ? 1 : 0)}`
            );
          }

          const isHighlighted = highlightedCategory === category;
          const isExpanded = expandedCategories[category] || false;

          // Group sources by name and count duplicates
          const sourceCounts = {};
          sources.forEach((source) => {
            const name = source.source;
            sourceCounts[name] = (sourceCounts[name] || 0) + 1;
          });

          const uniqueSources = Object.entries(sourceCounts).map(([name, count]) => ({
            name,
            count,
            display: count > 1 ? `${name} (${count})` : name,
          }));

          return (
            <div
              key={category}
              className={`aura-summary-item ${
                isHighlighted ? 'aura-summary-item-highlighted' : ''
              }`}
            >
              <div className="aura-summary-item-heading">
                <span className="aura-summary-category">{category}</span>
                {effects.length > 0 ? (
                  <span className="aura-summary-effects">{effects.join(' • ')}</span>
                ) : (
                  <span className="aura-summary-effects muted">
                    No stat changes
                  </span>
                )}
              </div>
              {sources.length > 0 && (
                <div className="aura-summary-sources-container">
                  <div className="aura-summary-sources">
                    {uniqueSources.slice(0, 4).map((source, idx) => (
                      <span key={`${category}-src-${idx}`} className="aura-summary-source-chip">
                        {source.display}
                      </span>
                    ))}
                  </div>
                  {uniqueSources.length > 4 && (
                    <button
                      className="aura-summary-expand-btn"
                      onClick={() => toggleExpanded(category)}
                      title={isExpanded ? 'Collapse' : 'Expand all sources'}
                    >
                      {isExpanded ? '▼' : '▶'} {uniqueSources.length - 4} more
                    </button>
                  )}
                  {isExpanded && uniqueSources.length > 4 && (
                    <div className="aura-summary-expanded-sources">
                      {uniqueSources.slice(4).map((source, idx) => (
                        <span key={`${category}-expanded-${idx}`} className="aura-summary-source-chip">
                          {source.display}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

AuraSummary.propTypes = {
  summary: PropTypes.arrayOf(
    PropTypes.shape({
      category: PropTypes.string.isRequired,
      income_multiplier: PropTypes.number,
      build_time_multiplier: PropTypes.number,
      operation_duration_multiplier: PropTypes.number,
      sources: PropTypes.arrayOf(
        PropTypes.shape({
          source: PropTypes.string,
        })
      ),
    })
  ),
  highlightedCategory: PropTypes.string,
};

AuraSummary.defaultProps = {
  summary: [],
  highlightedCategory: null,
};

export default AuraSummary;
