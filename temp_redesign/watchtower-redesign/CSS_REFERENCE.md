# 🎨 CSS Class Reference - WatchTower.ai Tactical Theme

## Complete Class Library

---

## 📐 **Layout & Structure**

### **Tactical Grid**
```css
.tactical-grid
```
**Usage**: Background grid overlay for tactical HUD aesthetic
**Example**:
```jsx
<div className="tactical-grid opacity-10"></div>
```

---

## 🃏 **Cards & Panels**

### **Tactical Card**
```css
.tactical-card
```
**Features**:
- Dark background (#0D0D0D)
- Gold muted border (#8B7355)
- Left accent bar on hover
- Elevation on hover
- Smooth transitions

**Example**:
```jsx
<div className="tactical-card p-6">
  <h3>Card Title</h3>
  <p>Content...</p>
</div>
```

---

## 🔘 **Buttons**

### **Tactical Button (Primary)**
```css
.btn-tactical
```
**Features**:
- Gold gradient background
- Black text
- Shine animation on hover
- Uppercase text
- Letter spacing
- Shadow on hover

**Example**:
```jsx
<button className="btn-tactical">
  Execute Command
</button>
```

---

## ✨ **Visual Effects**

### **Glow Effects**
```css
.glow-gold          /* Static gold glow */
.glow-gold-pulse    /* Pulsing gold glow animation */
```

**Examples**:
```jsx
<div className="glow-gold">Static glow</div>
<div className="glow-gold-pulse">Pulsing glow</div>
```

### **Scan Line**
```css
.scan-line
```
**Usage**: Animated horizontal scan effect
**Example**:
```jsx
<div className="scan-line">
  {/* Content being scanned */}
</div>
```

### **Loading Scanner**
```css
.loading-scanner
```
**Usage**: Gold animated loading bar
**Example**:
```jsx
<div className="loading-scanner"></div>
```

### **Data Stream**
```css
.data-stream
```
**Usage**: Vertical flowing data effect
**Example**:
```jsx
<div className="data-stream">
  {/* Streaming data content */}
</div>
```

---

## 🎯 **Status Indicators**

### **Active Status**
```css
.status-active
```
**Features**:
- Green background (#00FF41)
- Pulsing dot indicator
- Uppercase text
- Letter spacing

**Example**:
```jsx
<div className="status-active">LIVE</div>
```

### **Alert Status**
```css
.status-alert
```
**Features**:
- Red background (#FF3B3B)
- Blinking animation
- Uppercase text
- Letter spacing

**Example**:
```jsx
<div className="status-alert">ALERT</div>
```

---

## 🏷️ **Badges & Labels**

### **Gold Badge**
```css
.badge-gold
```
**Features**:
- Small compact size
- Gold gradient
- Black text
- Uppercase
- Rounded corners (minimal)

**Example**:
```jsx
<span className="badge-gold">NEW</span>
<span className="badge-gold">PRO</span>
```

---

## 📏 **Dividers**

### **Gold Divider**
```css
.divider-gold
```
**Features**:
- Horizontal gradient line
- Gold center fade
- Transparent edges
- 24px vertical margin

**Example**:
```jsx
<div className="divider-gold"></div>
```

---

## 🔲 **Special Shapes**

### **Hexagonal Border**
```css
.hex-border
```
**Features**:
- Clip-path hexagon shape
- Use for avatars or special elements

**Example**:
```jsx
<div className="hex-border w-20 h-20 bg-[#D4AF37]"></div>
```

### **Tactical Corners**
```css
.tactical-corners
```
**Features**:
- Corner bracket overlays
- Gold borders
- Positioned absolutely

**Example**:
```jsx
<div className="tactical-corners p-6">
  {/* Content with corner brackets */}
</div>
```

---

## 📝 **Form Elements**

### **Tactical Input**
```css
.input-tactical
```
**Features**:
- Full width
- Dark background
- Gold muted border
- Gold focus border
- Gold placeholder text

**Example**:
```jsx
<input 
  type="text"
  className="input-tactical"
  placeholder="Enter query..."
/>
```

---

## 🎪 **HUD Display**

### **HUD Container**
```css
.hud-display
```
**Features**:
- Dark semi-transparent background
- Gold border (2px)
- Clipped corners (angular)
- Padding included

**Example**:
```jsx
<div className="hud-display">
  <h2>System Status</h2>
  <p>All systems operational</p>
</div>
```

---

## 💬 **Tooltip**

### **Tactical Tooltip**
```css
.tooltip-tactical
```
**Usage**: Add `data-tooltip` attribute
**Example**:
```jsx
<button 
  className="tooltip-tactical"
  data-tooltip="Click to execute"
>
  Execute
</button>
```

---

## 🎨 **Color Classes (Tailwind)**

### **Backgrounds**
```
bg-black          /* #000000 - Pure black */
bg-[#0D0D0D]      /* Card backgrounds */
bg-[#141414]      /* Elevated surfaces */
bg-[#0A0A0A]      /* Subtle variation */
```

### **Borders**
```
border-[#8B7355]  /* Muted gold - default */
border-[#D4AF37]  /* Primary gold - active */
border-[#B8962E]  /* Dark gold */
border-[#F4D03F]  /* Light gold */
```

### **Text Colors**
```
text-white         /* Primary text */
text-gray-400      /* Secondary text */
text-[#D4AF37]     /* Gold accent */
text-[#8B7355]     /* Muted gold */
text-[#00FF41]     /* Green (live) */
text-[#FF3B3B]     /* Red (alert) */
```

---

## 🎯 **Utility Combinations**

### **Panel Header**
```jsx
<div className="px-6 py-4 border-b border-[#8B7355] flex justify-between items-center">
  <span className="text-xs text-[#D4AF37] uppercase tracking-wider font-semibold">
    SECTION TITLE
  </span>
</div>
```

### **Accent Bar**
```jsx
<div className="w-2 h-8 bg-gradient-to-b from-[#D4AF37] to-[#B8962E]"></div>
```

### **Corner Marker**
```jsx
<div className="absolute top-0 left-0 w-8 h-8 border-l-2 border-t-2 border-[#D4AF37]"></div>
```

### **Horizontal Gradient Line**
```jsx
<div className="h-px bg-gradient-to-r from-transparent via-[#D4AF37] to-transparent"></div>
```

### **Icon Container**
```jsx
<div className="w-12 h-12 flex items-center justify-center bg-[#D4AF37]/10 border border-[#D4AF37]">
  <Icon size={24} className="text-[#D4AF37]" />
</div>
```

---

## 🔄 **Animations**

### **Animation Classes**
```css
/* These are applied automatically by parent classes */
glowPulse        /* Used by .glow-gold-pulse */
scan             /* Used by .scan-line */
dataFlow         /* Used by .data-stream */
pulse            /* Used by .status-active */
alertBlink       /* Used by .status-alert */
scanLoad         /* Used by .loading-scanner */
```

### **Manual Animation Application**
```jsx
<div className="animate-pulse">Pulsing element</div>
<div className="animate-spin">Spinning element</div>
```

---

## 📱 **Responsive Patterns**

### **Spacing Progression**
```
p-4 sm:p-6 md:p-8        /* Padding */
mb-6 sm:mb-8 md:mb-12    /* Margin bottom */
gap-3 sm:gap-4 md:gap-6  /* Gap */
```

### **Layout Switches**
```
flex flex-col lg:flex-row              /* Stack → Row */
grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3  /* 1 → 2 → 3 columns */
hidden md:block                        /* Hide mobile, show desktop */
block md:hidden                        /* Show mobile, hide desktop */
```

### **Text Sizing**
```
text-xs sm:text-sm                     /* Small text */
text-sm sm:text-base                   /* Body text */
text-2xl sm:text-3xl md:text-4xl      /* Headings */
```

---

## 🎓 **Best Practices**

### **DO**
✅ Use `.tactical-card` for all card components
✅ Use `.btn-tactical` for primary CTAs
✅ Apply uppercase + tracking for labels
✅ Use gold colors sparingly for accents
✅ Add loading states with `.loading-scanner`
✅ Include tactical corners on key panels
✅ Use consistent spacing (4, 6, 8, 12, 16, 24)

### **DON'T**
❌ Mix multiple glow effects on same element
❌ Overuse animations (keep it subtle)
❌ Use rounded corners excessively
❌ Apply bright colors (stick to gold/black)
❌ Forget responsive classes
❌ Stack too many borders
❌ Use playful/casual typography

---

## 🔍 **Quick Search**

| Need | Use This Class |
|------|----------------|
| Card/Panel | `.tactical-card` |
| Button | `.btn-tactical` |
| Loading | `.loading-scanner` |
| Live Badge | `.status-active` |
| Alert Badge | `.status-alert` |
| Small Label | `.badge-gold` |
| Divider | `.divider-gold` |
| Input Field | `.input-tactical` |
| Background Grid | `.tactical-grid` |
| Corner Brackets | `.tactical-corners` |
| Glow Effect | `.glow-gold` |
| Scan Effect | `.scan-line` |
| HUD Panel | `.hud-display` |

---

## 💡 **Pro Tips**

1. **Combine classes** for compound effects:
   ```jsx
   <div className="tactical-card glow-gold-pulse">
     Enhanced card with glow
   </div>
   ```

2. **Layer backgrounds** for depth:
   ```jsx
   <div className="bg-black border border-[#8B7355]">
     <div className="bg-[#0D0D0D] p-6">
       Content
     </div>
   </div>
   ```

3. **Use CSS variables** in custom styles:
   ```css
   .custom-element {
     background: var(--gold-primary);
     border: var(--border-gold);
   }
   ```

4. **Stack tactical elements**:
   ```jsx
   <div className="relative tactical-corners">
     <div className="tactical-grid opacity-10"></div>
     <div className="scan-line">
       {/* Content */}
     </div>
   </div>
   ```

---

**WatchTower.ai Tactical Theme v2.0**
Complete CSS Class Reference Guide
