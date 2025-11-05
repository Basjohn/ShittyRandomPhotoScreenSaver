# START HERE - ShittyRandomPhotoScreenSaver

**Welcome to the comprehensive planning documentation for ShittyRandomPhotoScreenSaver!**

This document serves as your entry point to understand the project structure, planning documents, and implementation approach.

---

## Quick Start

### What is this project?

A modern, feature-rich Windows screensaver built with PySide6 that displays photos from local folders or RSS feeds with:
- Advanced transitions (including a 3D block puzzle flip effect)
- Multi-monitor support
- Overlay widgets (clock and weather)
- Professional dark-themed configuration UI

### Key Features
✨ **Multiple image sources** (local folders + RSS feeds)  
✨ **Advanced transitions** (crossfade, slide, diffuse, block puzzle flip)  
✨ **Multi-monitor support** (same or different images per display)  
✨ **Overlay widgets** (customizable clock and weather)  
✨ **Pan & scan** animation across zoomed images  
✨ **Professional UI** with instant save and dark theme  

---

## Documentation Structure

### Planning Documents (Read in Order)

These documents provide complete implementation guidance:

#### 1️⃣ **00_PROJECT_OVERVIEW.md**
- Project objectives and scope
- Key features summary
- Technology stack
- Success criteria
- Timeline overview

#### 2️⃣ **01_ARCHITECTURE_DESIGN.md**
- Complete directory structure
- Architecture principles
- Key components and responsibilities
- Data flow diagrams
- Integration points

#### 3️⃣ **02_REUSABLE_MODULES_INTEGRATION.md**
- Integration plan for `MyReuseableUtilityModules/`
- Module-by-module adaptation guide
- Import path updates
- Testing strategy
- Completion marker

#### 4️⃣ **03_CORE_IMPLEMENTATION.md**
- ScreensaverEngine implementation
- DisplayManager implementation
- ImageQueue implementation
- Command-line handling
- Logging configuration

#### 5️⃣ **04_IMAGE_SOURCES.md**
- Abstract ImageProvider interface
- FolderSource implementation
- RSSSource implementation
- Image caching strategy

#### 6️⃣ **05_DISPLAY_AND_RENDERING.md**
- DisplayWidget implementation
- ImageProcessor (Fill/Fit/Shrink modes)
- Pan & Scan animator
- Multi-monitor utilities

#### 7️⃣ **06_TRANSITIONS.md**
- BaseTransition interface
- All transition implementations
- Transition factory
- Testing strategies

#### 8️⃣ **07_WIDGETS_AND_UI.md**
- ClockWidget implementation
- WeatherWidget implementation
- SettingsDialog and all tabs
- Preview mode

#### 9️⃣ **08_TESTING_AND_DEPLOYMENT.md**
- Testing strategy (logging-first policy)
- Unit test structure
- PowerShell pytest patterns
- PyInstaller build process
- Windows installation

#### 🔟 **09_IMPLEMENTATION_ORDER.md**
- Day-by-day implementation plan
- Checkboxes for tracking progress
- 28-day timeline
- Checkpoint verification

### Reference Documents

#### **INDEX.md** (Living Document)
Complete module index with:
- All modules and their purposes
- Key classes and functions
- Dependencies graph
- Quick lookup guide
- Update checklist

**⚠️ Update INDEX.md after any major structural changes**

#### **SPEC.md** (Single Source of Truth)
Technical specification with:
- All functional requirements
- Non-functional requirements
- Architecture details
- Settings schema
- File structure
- Testing requirements
- Error handling strategy

**⚠️ SPEC.md is the authoritative source - all implementation must conform to this spec**

---

## How to Use This Documentation

### If you're starting implementation:

1. **Read** `00_PROJECT_OVERVIEW.md` - understand what we're building
2. **Read** `01_ARCHITECTURE_DESIGN.md` - understand how it's structured
3. **Follow** `09_IMPLEMENTATION_ORDER.md` - implement step-by-step with checkboxes
4. **Reference** `INDEX.md` - find modules and functions quickly
5. **Reference** `SPEC.md` - verify requirements and constraints
6. **Reference** implementation documents (03-08) - get detailed code examples

### If you're modifying existing code:

1. **Check** `INDEX.md` - find the module you need
2. **Read** relevant implementation document (03-08)
3. **Verify** against `SPEC.md` - ensure changes align with requirements
4. **Update** `INDEX.md` if structure changes
5. **Update** tests in `tests/`

### If you're debugging:

1. **Check** logs in `logs/` directory (logging-first policy)
2. **Reference** `INDEX.md` - understand module dependencies
3. **Read** `08_TESTING_AND_DEPLOYMENT.md` - proper testing procedures
4. **Use** PowerShell pytest patterns (not direct terminal output)

---

## Project Principles

### From User Rules

These are the core principles that guide all development:

#### 1. NO MORE THAN 2 CONCURRENT ACTIONS
Never run more than 2 parallel operations at once.

#### 2. LOGGING-FIRST POLICY
Terminal output is unreliable. Always log to files. Read logs for debugging.

#### 3. CENTRALIZED ARCHITECTURE
- ThreadManager for all async operations
- ResourceManager for all resource cleanup
- EventSystem for all cross-module communication
- SettingsManager for all configuration

#### 4. NO SILENT FALLBACKS
If something fails, log it explicitly. No hiding errors.

#### 5. INDEX.MD IS A LIVING DOCUMENT
Update it after major changes. It's not a changelog - it's a current state map.

#### 6. SPEC.MD IS NOT A CHANGELOG
It's the single source of truth for what the application should be.

#### 7. REUSABLE MODULES
- Copy from `MyReuseableUtilityModules/`
- Adapt for screensaver use
- DO NOT EDIT originals in place
- Delete or .gitignore when integration complete

---

## Technology Stack

### Core Technologies
- **PySide6** (Qt 6.x) - UI framework
- **Python 3.9+** - Programming language
- **Windows 11** - Target platform

### Key Libraries
- **requests** - HTTP for RSS/weather
- **pytz** - Timezone support
- **pytest** - Testing framework
- **pytest-qt** - Qt testing support

### Architecture Patterns
- Event-driven architecture
- Lock-free concurrency
- Centralized resource management
- Dependency injection
- Abstract base classes

---

## Development Timeline

### 6-Week Plan

**Week 1**: Foundation + Image Sources
- Days 1-2: Core modules integration
- Days 3-4: Folder and RSS sources
- Day 5: Image processing

**Week 2**: Display + Engine + Basic Transitions
- Day 6: Display widget
- Days 7-8: Basic engine
- Days 9-11: All transitions

**Week 3**: Advanced Features
- Days 12-13: Pan & scan
- Days 14-16: Overlay widgets

**Week 4**: Configuration UI
- Days 17-21: Complete settings dialog with all tabs

**Week 5**: Testing & Polish
- Days 22-25: Testing, optimization, bug fixes

**Week 6**: Deployment
- Days 26-28: Build, package, final testing

---

## Critical Checkpoints

These are the verification points where you should test before proceeding:

✅ **After Day 1**: All core systems work independently  
✅ **After Day 2**: Can detect monitors and parse arguments  
✅ **After Day 4**: Can load images from folders  
✅ **After Day 6**: Can display images fullscreen on all monitors  
✅ **After Day 8**: Basic slideshow works with instant transitions  
✅ **After Day 11**: All transitions work smoothly  
✅ **After Day 13**: Pan & scan works smoothly  
✅ **After Day 16**: Clock and weather overlays work  
✅ **After Day 21**: Complete configuration UI works  
✅ **After Day 25**: All features work, tests pass  
✅ **After Day 27**: Deployable package ready  

---

## File Organization

```
ShittyRandomPhotoScreenSaver/
├── Docs/                          # THIS DIRECTORY - All planning docs
│   ├── 00_START_HERE.md           # ← YOU ARE HERE
│   ├── 00_PROJECT_OVERVIEW.md
│   ├── 01_ARCHITECTURE_DESIGN.md
│   ├── 02_REUSABLE_MODULES_INTEGRATION.md
│   ├── 03_CORE_IMPLEMENTATION.md
│   ├── 04_IMAGE_SOURCES.md
│   ├── 05_DISPLAY_AND_RENDERING.md
│   ├── 06_TRANSITIONS.md
│   ├── 07_WIDGETS_AND_UI.md
│   ├── 08_TESTING_AND_DEPLOYMENT.md
│   ├── 09_IMPLEMENTATION_ORDER.md
│   ├── INDEX.md                   # Living module index
│   ├── SPEC.md                    # Technical spec (source of truth)
│   ├── initial_screensaver_plan.md
│   └── settings_gui.txt
│
├── main.py                        # WILL BE CREATED
├── requirements.txt               # WILL BE CREATED
├── screensaver.spec              # WILL BE CREATED
├── README.md                      # WILL BE CREATED
│
├── core/                          # WILL BE CREATED (adapted from reusables)
├── engine/                        # WILL BE CREATED
├── sources/                       # WILL BE CREATED
├── rendering/                     # WILL BE CREATED
├── transitions/                   # WILL BE CREATED
├── widgets/                       # WILL BE CREATED
├── ui/                           # WILL BE CREATED
├── utils/                        # WILL BE CREATED
├── themes/                       # WILL BE CREATED
├── tests/                        # WILL BE CREATED
├── logs/                         # Created at runtime
│
└── MyReuseableUtilityModules/    # EXISTS - Copy modules from here
    └── (to be deleted or .gitignored after integration)
```

---

## Testing Strategy

### Logging-First Policy

**CRITICAL**: Terminal output is unreliable on Windows. Always use logging.

#### PowerShell Pattern for Pytest
```powershell
# Start pytest with logging
$job = Start-Job -ScriptBlock { 
    pytest -vv --maxfail=2 *>&1 | Out-File -FilePath pytest.log -Encoding utf8 
};

# Wait with timeout
$null = Wait-Job -Id $job.Id -Timeout 30;

# Stop if still running
if ($job.State -ne 'Completed') {
    Stop-Job -Id $job.Id -ErrorAction SilentlyContinue;
}

# Cleanup job
Remove-Job -Id $job.Id -ErrorAction SilentlyContinue;

# Read log
if (Test-Path pytest.log) {
    Get-Content pytest.log -Tail 50;
} else {
    Write-Host "pytest.log not found";
}
```

### Test Categories
1. **Unit Tests** - Individual modules (threading, resources, events, settings, etc.)
2. **Integration Tests** - Complete workflows
3. **Performance Tests** - Memory usage, FPS, long-duration
4. **Manual Tests** - UI, transitions, preview mode

---

## Reusable Modules Integration

### Source: `MyReuseableUtilityModules/`

These modules are **production-tested** from SPQDocker and need to be adapted:

1. ✅ **ThreadManager** - Lock-free threading with specialized pools
2. ✅ **ResourceManager** - Deterministic resource cleanup
3. ✅ **EventSystem** - Publish-subscribe event bus
4. ✅ **SettingsManager** - Type-safe configuration
5. ✅ **Logging utilities** - Centralized logging
6. ✅ **dark.qss theme** - Complete dark theme
7. ⚠️ **Monitor utilities** - Extract relevant parts only

### Integration Steps

1. Copy module from `MyReuseableUtilityModules/` to `core/`
2. Update import paths
3. Adapt for screensaver use case
4. Test independently
5. When ALL modules integrated, mark completion in `02_REUSABLE_MODULES_INTEGRATION.md`
6. Delete or .gitignore `MyReuseableUtilityModules/`

---

## Common Patterns

### Adding a New Component

1. Create module file
2. Add to `INDEX.md` with purpose and key classes
3. Add unit tests in `tests/`
4. Update `SPEC.md` if requirements change
5. Document in relevant planning doc (03-08)

### Debugging Issues

1. Check `logs/screensaver.log` (NOT terminal output)
2. Find module in `INDEX.md`
3. Review implementation in planning docs
4. Add logging if needed
5. Run focused tests with logging

### Making Changes

1. Verify against `SPEC.md` requirements
2. Update implementation
3. Update tests
4. Update `INDEX.md` if structure changes
5. Run test suite with logging

---

## Success Criteria

The project is complete when:

✅ All functional requirements in `SPEC.md` are met  
✅ All transitions run at 60 FPS on 1080p  
✅ Memory usage < 500MB  
✅ Startup time < 2 seconds  
✅ All tests pass  
✅ Can install as .scr in Windows  
✅ Preview mode works in Windows settings  
✅ All reusable modules integrated and cleaned up  

---

## Next Steps

### To Begin Implementation:

1. **Read** `00_PROJECT_OVERVIEW.md` (5 minutes)
2. **Read** `01_ARCHITECTURE_DESIGN.md` (10 minutes)
3. **Open** `09_IMPLEMENTATION_ORDER.md` (this is your roadmap)
4. **Start** with Day 1: Project Structure & Core Modules
5. **Check off** tasks as you complete them
6. **Reference** other docs as needed

### First Day Goals:

- [ ] Create directory structure
- [ ] Copy and adapt ThreadManager
- [ ] Copy and adapt ResourceManager
- [ ] Copy and adapt EventSystem
- [ ] Copy and adapt SettingsManager
- [ ] Copy logging utilities
- [ ] Copy dark.qss theme
- [ ] Create and run basic tests

---

## Support & Reference

### Need to find something quickly?
→ Check **INDEX.md**

### Need to verify a requirement?
→ Check **SPEC.md**

### Need implementation details?
→ Check **relevant planning doc (03-08)**

### Need to know what to do next?
→ Check **09_IMPLEMENTATION_ORDER.md**

### Stuck on testing?
→ Check **08_TESTING_AND_DEPLOYMENT.md**

---

## Important Reminders

🔴 **NO MORE THAN 2 CONCURRENT ACTIONS** - Keep operations sequential  
🔴 **LOGGING-FIRST POLICY** - Always log, never rely on terminal output  
🔴 **UPDATE INDEX.MD** - Keep it current with structure changes  
🔴 **SPEC.MD IS LAW** - All implementation must conform to spec  
🔴 **TEST AFTER CHECKPOINTS** - Verify before moving forward  
🔴 **DELETE REUSABLES WHEN DONE** - Mark completion and cleanup  

---

## Project Status

**Current Phase**: Planning Complete  
**Next Step**: Begin Day 1 Implementation  
**Reusable Modules Status**: Not yet integrated  

---

**You have everything you need to build this screensaver. The planning is complete, comprehensive, and ready for implementation. Good luck! 🚀**
