export const gameInfoContent = `
<h1>🏛️ Welcome to TycoonCraft!</h1>

<h2>About the Game</h2>
<p>
TycoonCraft is a civilization-building crafting game where you combine objects to discover new items,
build your empire, and progress through ten eras of human history—from Hunter-Gatherer all the way to Beyond!
</p>

<p>
Created by <strong>Alex</strong>, TycoonCraft combines the satisfaction of discovery with strategic resource management.
Every combination you try might unlock something new, and every object you place generates resources to fuel your civilization's growth.
Powered by AI, each crafting result is dynamically generated based on your inputs!
</p>

<h2>How to Play</h2>

<h3>🎯 Getting Started</h3>
<ol>
  <li><strong>Discover Objects:</strong> You start with basic starter objects. Drag any two objects
  to the crafting slots and click "Craft" to discover new items!</li>
  <li><strong>Crafting Costs:</strong> Each craft costs coins (increases with each era). Watch your coin balance in the top bar.</li>
  <li><strong>Place Objects:</strong> Once discovered, drag objects from the sidebar onto the canvas grid to place them.
  Objects will build over time, then become operational and generate coins and time crystals.</li>
  <li><strong>Manage Resources:</strong> Coins let you craft and place more objects. Time crystals (💎) unlock new eras.</li>
</ol>

<h3>⚗️ Crafting System</h3>
<ul>
  <li><strong>Combine any two discovered objects</strong> to create something new via AI generation</li>
  <li><strong>Global discoveries:</strong> If someone else already crafted this combination, you'll get their result instantly</li>
  <li><strong>Era restrictions:</strong> You can only combine objects from the SAME era. The result will belong to that era.</li>
  <li><strong>Queue system:</strong> Crafts are added to a queue. Each craft takes time, but you can queue multiple at once.</li>
  <li><strong>Rate limits:</strong> Standard players get 20 AI crafts/day, Pro players get 500/day. There's also a global daily limit.</li>
  <li><strong>Inspect objects:</strong> Click the ℹ️ icon on any object in the sidebar to see detailed stats before placing</li>
</ul>

<h3>🗺️ Canvas Placement</h3>
<ul>
  <li><strong>Grid-based canvas:</strong> Starts at 1000×1000 grid units. Drag objects from sidebar to place them.</li>
  <li><strong>Object lifecycle:</strong> Objects have build time → operational period → retirement. They generate income while operational.</li>
  <li><strong>Footprint matters:</strong> Each object has width×height. Plan your layout to maximize space!</li>
  <li><strong>Remove objects:</strong> Click placed objects to remove them and get a partial coin refund (sellback value).</li>
  <li><strong>Zoom & Pan:</strong> Use zoom controls to navigate. Drag the canvas to pan around.</li>
  <li><strong>Placement caps:</strong> Some powerful objects have limited placement counts (check "Cap/Civ" stat).</li>
</ul>

<h3>🚀 Era Progression</h3>
<ul>
  <li><strong>10 Eras:</strong> Hunter-Gatherer → Agriculture → Metallurgy → Steam & Industry →
  Electric Age → Computing → Futurism → Interstellar → Arcana → Beyond</li>
  <li><strong>Keystone objects (🔑):</strong> Special objects that automatically unlock the NEXT era when placed and operational</li>
  <li><strong>Example keystone path:</strong> Start with Rock, Stick, Water, Dirt → find Fire + Wood = Campfire (keystone) → place it to unlock Agriculture!</li>
  <li><strong>Manual unlock:</strong> You can also spend time crystals to manually unlock eras via the era button</li>
  <li><strong>Crafting costs increase:</strong> Each era has higher crafting costs (Hunter-Gatherer: 100 coins, Agriculture: 750 coins, etc.)</li>
</ul>

<h3>🔮 Aura System (Agriculture+)</h3>
<ul>
  <li><strong>Unlocks in Agriculture era:</strong> Some objects have "aura effects" that boost other objects!</li>
  <li><strong>Category targeting:</strong> Auras affect specific categories (e.g., farms, tools, buildings, magic)</li>
  <li><strong>Stat multipliers:</strong> Auras can boost income, reduce build time, extend lifespan, or reduce costs</li>
  <li><strong>Activation conditions:</strong> Auras activate "while placed" or "while operational"</li>
  <li><strong>Stacking:</strong> Multiple auras can stack (either additively or multiplicatively). Some have max stacks.</li>
  <li><strong>View active auras:</strong> Check the "🔮 Active Auras" panel to see what's currently affecting your buildings</li>
</ul>

<h3>💡 Tips & Strategies</h3>
<ul>
  <li><strong>Experiment wisely:</strong> You have limited AI crafts per day—try logical combinations first!</li>
  <li><strong>Build an economy:</strong> Place objects with good income/sec to generate coins for more crafting</li>
  <li><strong>Crystal generation:</strong> Some objects generate time crystals—essential for era progression</li>
  <li><strong>Space efficiency:</strong> Smaller footprints let you place more objects. Balance size vs. income.</li>
  <li><strong>Search function:</strong> Use the search bar in the sidebar to quickly find discovered objects</li>
  <li><strong>Keystones first:</strong> Prioritize finding and placing keystone objects to unlock new eras and their powerful bonuses</li>
  <li><strong>Aura synergies:</strong> In later eras, build around aura effects to massively boost your economy</li>
</ul>

<h3>🎨 Customization</h3>
<ul>
  <li><strong>Theme switcher:</strong> Click the theme button to toggle between light and dark modes</li>
  <li><strong>Custom colors:</strong> Long-press the theme button to choose from multiple color schemes!</li>
  <li><strong>Save/Load:</strong> Export your game state as JSON to back up progress, or import a save file to restore</li>
</ul>

<h3>⚡ Pro Upgrade</h3>
<ul>
  <li><strong>Upgrade keys:</strong> Redeem a key to unlock Pro status (500 AI crafts/day vs. 20 standard)</li>
  <li><strong>Get keys:</strong> Contact the developer or check for promotional offers</li>
</ul>

<h2>Need Help?</h2>
<p>
Have questions, feedback, or suggestions? Alex would love to hear from you!<br/>
Email: <a href="mailto:help@tycooncraft.com">help@tycooncraft.com</a>
</p>

<p style="text-align: center; margin-top: 2rem; color: var(--text-secondary);">
<em>Happy crafting, and may your civilization prosper! 🎮</em>
</p>
`;
