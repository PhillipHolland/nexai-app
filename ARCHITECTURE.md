# LexAI Application Architecture

## 🏗️ File Structure

### Core Application Files
- `/api/index.py` - Main Flask application with all routes and API endpoints
- `/templates/` - Jinja2 HTML templates
- `/static/` - CSS, JavaScript, and static assets

### Key Templates
- `landing.html` - Homepage (standalone, uses landing.css)
- `base.html` - Base template for authenticated pages (extends to other templates)
- `dashboard.html` - Main user dashboard
- `onboarding.html` - User registration flow

### CSS Files
- `landing.css` - Homepage and landing page styles
- `style.css` - General utility classes and color definitions
- `platform.css` - Platform-specific styles

## 🎨 CSS Architecture

### Class Naming Conventions
- `.btn-primary` - Primary action buttons (orange background, dark text)
- `.btn-secondary` - Secondary buttons (transparent with border)
- `.btn-outline` - Outline buttons for pricing cards
- `.integration-*` - Integration section specific classes
- `.nav-*` - Navigation related classes

### CSS Hierarchy (specificity order)
1. Browser defaults
2. Base reset styles
3. Component styles (buttons, cards, etc.)
4. Layout styles (containers, grids)
5. Page-specific styles
6. Responsive overrides

### Avoiding CSS Conflicts
- ✅ Use specific class names instead of generic selectors
- ✅ Avoid `!important` unless absolutely necessary
- ✅ Test changes on both landing.html and base.html templates
- ❌ Don't use escaped quotes in HTML: `class=\"name\"` (breaks CSS)
- ❌ Don't duplicate CSS rules across files

## 🔄 Template System

### Standalone Templates
- `landing.html` - Complete HTML document with its own CSS
- `landing-law-firms.html` - Law firm specific landing page
- `pricing.html` - Pricing page

### Extended Templates (use base.html)
- Most dashboard and authenticated pages
- Automatically inherit base.html styles and navigation

## 🚨 Common Issues & Solutions

### CSS Not Applying
1. Check for escaped quotes in HTML: `class=\"name\"`
2. Verify CSS file is being loaded with cache buster
3. Check for conflicting `!important` declarations
4. Ensure proper CSS specificity

### Template Conflicts
- Landing pages are standalone - don't extend base.html
- Dashboard pages extend base.html
- Never mix the two approaches

### Button Text Visibility
- Light text on light backgrounds: Use dark text colors
- Dark text on dark backgrounds: Use light text colors
- Test button contrast on all background colors

## 📝 Development Guidelines

### Making CSS Changes
1. Identify which CSS file applies to your target page
2. Use specific class names rather than generic selectors
3. Test on both desktop and mobile
4. Avoid `!important` - use proper specificity instead
5. Commit and test deployment before making additional changes

### Adding New Pages
1. Decide: Standalone (like landing) or extends base.html?
2. Create appropriate CSS classes following naming conventions
3. Test responsive design
4. Document any new class names in this file

### Safe Deployment Process
1. Make changes locally
2. Test in development
3. Commit with descriptive message
4. Push and verify on production
5. Document any new patterns or fixes

## 🏷️ Color System
- `#F7EDDA` - Light cream (backgrounds, containers)
- `#2E4B3C` - Dark green (primary text, buttons)
- `#FFA74F` - Warm orange (accent color, featured elements)
- `#1f2937` - Dark gray (headings, primary text)
- `#6b7280` - Medium gray (secondary text)

## 📱 Responsive Breakpoints
- Desktop: Default styles
- Tablet: 768px and below
- Mobile: Specific adjustments within tablet breakpoint

---

Last updated: July 11, 2025